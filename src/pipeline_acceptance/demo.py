"""Reproducible baseline-versus-guarded experiment; outputs explicit evidence JSON."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .preflight import TestDatabaseUnavailable, require_postgres_ready
from .guarded import accept_validated_dataset, process_once, try_mark_running
from .legacy import AckLostAfterCommit, process_with_bug, stale_running_update_with_bug, update_dataset_with_bug
from .storage import (
    get_dataset, get_effect_count, get_status, isolated_engine, seed_dataset, seed_job,
)


def run_cases(dsn: str | None = None) -> dict:
    with isolated_engine(dsn) as engine:
        backend = engine.dialect.name
        scenarios = []
        seed_job(engine, "legacy_replay")
        try:
            process_with_bug(engine, "legacy_replay", "legacy-key", "sent", crash_after_commit=True)
        except AckLostAfterCommit:
            pass
        process_with_bug(engine, "legacy_replay", "legacy-key", "sent")
        legacy_count = get_effect_count(engine, "legacy-key", legacy=True)
        seed_job(engine, "fixed_replay")
        try:
            process_once(engine, "fixed_replay", "fixed-key", "sent", crash_after_commit=True)
        except AckLostAfterCommit:
            pass
        process_once(engine, "fixed_replay", "fixed-key", "sent")
        fixed_count = get_effect_count(engine, "fixed-key")
        scenarios.append({"id": "commit_before_ack_then_replay", "invariant": "one durable effect per logical key", "legacy_observed": legacy_count, "guarded_observed": fixed_count, "legacy_violates": legacy_count != 1, "guarded_passes": fixed_count == 1})

        seed_job(engine, "legacy_stale", "RUNNING")
        process_with_bug(engine, "legacy_stale", "stale-key", "sent")
        stale_running_update_with_bug(engine, "legacy_stale")
        legacy_state = get_status(engine, "legacy_stale")
        seed_job(engine, "fixed_stale", "RUNNING")
        process_once(engine, "fixed_stale", "fixed-stale-key", "sent")
        stale_was_accepted = try_mark_running(engine, "fixed_stale")
        fixed_state = get_status(engine, "fixed_stale")
        scenarios.append({"id": "stale_running_after_success", "invariant": "terminal status must not regress", "legacy_observed": legacy_state, "guarded_observed": fixed_state, "guarded_stale_transition_accepted": stale_was_accepted, "legacy_violates": legacy_state != "SUCCEEDED", "guarded_passes": fixed_state == "SUCCEEDED" and not stale_was_accepted})

        seed_job(engine, "legacy_validation")
        seed_dataset(engine, "legacy_slot", "good-v1")
        try:
            update_dataset_with_bug(engine, "legacy_validation", "legacy_slot", "invalid-data", valid=False)
        except ValueError:
            pass
        legacy_dataset = get_dataset(engine, "legacy_slot")
        seed_job(engine, "fixed_validation")
        seed_dataset(engine, "fixed_slot", "good-v1")
        try:
            accept_validated_dataset(engine, "fixed_validation", "fixed_slot", "invalid-data", valid=False)
        except ValueError:
            pass
        fixed_dataset = get_dataset(engine, "fixed_slot")
        scenarios.append({"id": "invalid_candidate_cannot_replace_good_data", "invariant": "validation failure preserves accepted data", "legacy_observed": {"value": legacy_dataset[0], "revision": legacy_dataset[1]}, "guarded_observed": {"value": fixed_dataset[0], "revision": fixed_dataset[1]}, "legacy_violates": legacy_dataset != ("good-v1", 1), "guarded_passes": fixed_dataset == ("good-v1", 1)})

    return {
        "experiment": "python-pipeline-acceptance",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "evidence_scope": "isolated synthetic demonstration; not a customer application; no benchmark/ROI proof",
        "pass": all(x["legacy_violates"] and x["guarded_passes"] for x in scenarios),
        "scenarios": scenarios,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres", action="store_true", help="Use local disposable PostgreSQL; DSN read only from PIPELINE_TEST_DSN")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence report")
    args = parser.parse_args()
    if args.postgres and not os.environ.get("PIPELINE_TEST_DSN"):
        parser.error("--postgres requires PIPELINE_TEST_DSN environment variable")
    if args.postgres:
        try:
            require_postgres_ready(os.environ["PIPELINE_TEST_DSN"])
        except (TestDatabaseUnavailable, ValueError) as exc:
            parser.exit(2, f"PostgreSQL preflight failed: {exc}\n")
    result = run_cases(os.environ["PIPELINE_TEST_DSN"] if args.postgres else None)
    report = json.dumps(result, indent=2, ensure_ascii=False)
    print(report)
    if args.output:
        # Atomic replacement avoids following a symlink at the target path.
        # On POSIX, the temporary evidence file is created owner-readable only.
        target = args.output
        fd, temporary = tempfile.mkstemp(prefix=".pipeline-report-", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(report + "\n")
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
