"""Synthetic process-termination acceptance, using disposable SQL databases only.

The parent terminates a separate worker at two deterministic checkpoints.
This is NOT a generic chaos-testing engine or evidence of production safety.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, insert, update
from sqlalchemy.engine import Engine, URL

from .guarded import process_once
from .legacy import process_with_bug
from .preflight import TestDatabaseUnavailable, require_postgres_ready
from .storage import effects, enable_sqlite_foreign_keys, get_effect_count, get_status, isolated_engine, jobs, legacy_effects, seed_job, validate_local_test_dsn

_SCHEMA_RE = re.compile(r"acceptance_[0-9a-f]{24}\Z")
_CHECKPOINT_TIMEOUT = 12.0
_WORKER_HOLD_SECONDS = 45


def _worker_engine() -> Engine:
    """Attach ONLY to the parent's disposable SQLite DB or isolated PG schema."""
    if os.environ.get("PIPELINE_CRASH_CHILD") != "1":
        raise RuntimeError("Direct worker execution is disabled")
    backend = os.environ.get("PIPELINE_CRASH_BACKEND")
    if backend == "sqlite":
        db = os.environ.get("PIPELINE_CRASH_SQLITE_PATH")
        if not db or not Path(db).is_absolute() or not Path(db).is_file():
            raise RuntimeError("Worker requires an existing disposable SQLite database")
        engine = create_engine(URL.create("sqlite+pysqlite", database=db), hide_parameters=True)
        enable_sqlite_foreign_keys(engine)
        return engine
    if backend == "postgresql":
        dsn = os.environ.get("PIPELINE_TEST_DSN", "")
        validate_local_test_dsn(dsn)
        schema = os.environ.get("PIPELINE_CRASH_SCHEMA", "")
        if not _SCHEMA_RE.fullmatch(schema):
            raise RuntimeError("Worker requires a valid isolated test schema")
        raw = create_engine(
            dsn,
            hide_parameters=True,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5, "options": "-c statement_timeout=10000 -c lock_timeout=3000"},
        )
        return raw.execution_options(schema_translate_map={None: schema})
    raise RuntimeError("Worker backend is not permitted")


def _write_checkpoint(marker: Path, stage: str) -> None:
    """Publish marker atomically so parent cannot observe a partially written file."""
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(stage, encoding="ascii")
    os.replace(temporary, marker)


def _child(stage: str, job_id: str, logical_key: str, payload: str) -> None:
    if os.environ.get("PIPELINE_CRASH_CHILD") != "1":
        raise RuntimeError("Direct worker execution is disabled")
    checkpoint = os.environ.get("PIPELINE_CRASH_MARKER", "")
    if not checkpoint or not Path(checkpoint).is_absolute():
        raise RuntimeError("A parent-owned checkpoint file is required")
    engine = _worker_engine()
    implementation = os.environ.get("PIPELINE_CRASH_IMPLEMENTATION", "guarded")
    if implementation not in {"guarded", "legacy"}:
        raise RuntimeError("Unsupported test implementation")
    if stage == "before_commit":
        # Write inside an open transaction, but DO NOT COMMIT. The parent kills
        # the process while the transaction is open, so the DB must roll it back.
        conn = engine.connect()
        conn.begin()
        if implementation == "guarded":
            conn.execute(insert(effects).values(job_id=job_id, logical_key=logical_key, payload=payload))
        else:
            conn.execute(insert(legacy_effects).values(event_id=uuid4().hex, logical_key=logical_key, payload=payload))
        conn.execute(update(jobs).where(jobs.c.job_id == job_id).values(status="SUCCEEDED"))
        _write_checkpoint(Path(checkpoint), "before_commit")
    elif stage == "after_commit":
        # process_once returns only after COMMIT. The parent kills the child
        # immediately after this checkpoint, before any queue acknowledgement.
        if implementation == "guarded":
            process_once(engine, job_id, logical_key, payload)
        else:
            process_with_bug(engine, job_id, logical_key, payload)
        _write_checkpoint(Path(checkpoint), "after_commit")
    else:
        raise RuntimeError("Unsupported crash checkpoint")
    # This is deliberately not a voluntary exit: the parent must terminate us.
    time.sleep(_WORKER_HOLD_SECONDS)
    raise RuntimeError("Parent failed to terminate worker at checkpoint")


def _kill_at_checkpoint(engine: Engine, stage: str, job_id: str, logical_key: str, payload: str, *, implementation: str) -> int:
    env = dict(os.environ)
    env["PIPELINE_CRASH_CHILD"] = "1"
    env["PIPELINE_CRASH_BACKEND"] = engine.dialect.name
    env["PIPELINE_CRASH_IMPLEMENTATION"] = implementation
    if engine.dialect.name == "sqlite":
        db = engine.url.database
        if not db or db == ":memory:":
            raise RuntimeError("Process tests require file-backed disposable SQLite")
        env["PIPELINE_CRASH_SQLITE_PATH"] = str(Path(db).resolve())
        # Never switch to PostgreSQL based on an ambient env var.
        env.pop("PIPELINE_TEST_DSN", None)
        env.pop("PIPELINE_CRASH_SCHEMA", None)
    elif engine.dialect.name == "postgresql":
        dsn = env.get("PIPELINE_TEST_DSN", "")
        validate_local_test_dsn(dsn)
        schema = engine.get_execution_options().get("schema_translate_map", {}).get(None, "")
        if not isinstance(schema, str) or not _SCHEMA_RE.fullmatch(schema):
            raise RuntimeError("Parent must own an isolated PostgreSQL test schema")
        env["PIPELINE_CRASH_SCHEMA"] = schema
        env.pop("PIPELINE_CRASH_SQLITE_PATH", None)
    else:
        raise RuntimeError("Only SQLite and disposable PostgreSQL backends are supported")

    with tempfile.TemporaryDirectory(prefix="ppa-checkpoint-") as marker_dir:
        marker = Path(marker_dir) / "ready"
        env["PIPELINE_CRASH_MARKER"] = str(marker)
        args = [
            sys.executable, "-m", "pipeline_acceptance.crash_harness",
            "--child-stage", stage, "--job-id", job_id, "--logical-key", logical_key, "--payload", payload,
        ]
        proc = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + _CHECKPOINT_TIMEOUT
            while time.monotonic() < deadline:
                if marker.is_file():
                    if marker.read_text(encoding="ascii") != stage:
                        raise RuntimeError("Worker reached the wrong crash checkpoint")
                    if proc.poll() is not None:
                        raise RuntimeError("Worker exited without being killed by parent")
                    proc.kill()  # SIGKILL on POSIX / TerminateProcess on Windows
                    result = proc.wait(timeout=5)
                    if result == 0:
                        raise RuntimeError("Unexpected successful worker exit")
                    return result
                if proc.poll() is not None:
                    # The exit code is safe to disclose; child stdout/stderr and
                    # connection credentials remain suppressed.
                    raise RuntimeError(
                        f"Worker exited before {stage} checkpoint (exit code {proc.returncode}); test inconclusive"
                    )
                time.sleep(0.025)
            raise RuntimeError(f"Worker never reached {stage} checkpoint (timeout); test inconclusive")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)


def run_acceptance(engine: Engine, *, implementation: str = "guarded") -> dict:
    """Independently inspect durable rows after killing each separate worker.

    ``legacy`` is a known-broken negative control: it MUST fail after replay.
    """
    if implementation not in {"guarded", "legacy"}:
        raise ValueError("Unsupported test implementation")
    cases = []
    for stage in ("before_commit", "after_commit"):
        suffix = uuid4().hex[:12]
        job_id = f"crash-{stage}-{suffix}"
        logical_key = f"crash-key-{suffix}"
        payload = "synthetic-effect"
        seed_job(engine, job_id)
        exit_code = _kill_at_checkpoint(engine, stage, job_id, logical_key, payload, implementation=implementation)
        legacy = implementation == "legacy"
        before_replay_count = get_effect_count(engine, logical_key, legacy=legacy)
        before_replay_status = get_status(engine, job_id)
        if legacy:
            process_with_bug(engine, job_id, logical_key, payload)
        else:
            process_once(engine, job_id, logical_key, payload)
        after_replay_count = get_effect_count(engine, logical_key, legacy=legacy)
        after_replay_status = get_status(engine, job_id)
        expected_count = 0 if stage == "before_commit" else 1
        expected_state = "PENDING" if stage == "before_commit" else "SUCCEEDED"
        cases.append({
            "checkpoint": stage,
            "worker_terminated_by_parent": True,
            "worker_exit_code": exit_code,
            "effect_count_after_kill": before_replay_count,
            "status_after_kill": before_replay_status,
            "effect_count_after_replay": after_replay_count,
            "status_after_replay": after_replay_status,
            "pass": (
                before_replay_count == expected_count
                and before_replay_status == expected_state
                and after_replay_count == 1
                and after_replay_status == "SUCCEEDED"
            ),
        })
    return {
        "experiment": "python-pipeline-acceptance-process-crash",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": engine.dialect.name,
        "implementation": implementation,
        "evidence_scope": "synthetic disposable DB, real child-process termination; no production, queue, or ROI proof",
        "pass": all(case["pass"] for case in cases),
        "scenarios": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres", action="store_true", help="Opt in to disposable local PostgreSQL via PIPELINE_TEST_DSN")
    parser.add_argument("--output", type=Path, help="Write synthetic evidence JSON")
    # Internal worker command; never pass DB credentials on command line.
    parser.add_argument("--child-stage", choices=["before_commit", "after_commit"])
    parser.add_argument("--job-id")
    parser.add_argument("--logical-key")
    parser.add_argument("--payload")
    args = parser.parse_args()
    if args.child_stage:
        if args.postgres or args.output or not all((args.job_id, args.logical_key, args.payload)):
            parser.error("Invalid worker invocation")
        _child(args.child_stage, args.job_id, args.logical_key, args.payload)
        return
    if any((args.job_id, args.logical_key, args.payload)):
        parser.error("Worker arguments are internal only")

    dsn = None
    if args.postgres:
        dsn = os.environ.get("PIPELINE_TEST_DSN")
        if not dsn:
            parser.error("--postgres requires PIPELINE_TEST_DSN")
        try:
            require_postgres_ready(dsn)
        except (TestDatabaseUnavailable, ValueError) as exc:
            parser.exit(2, f"PostgreSQL preflight failed: {exc}\n")

    with tempfile.TemporaryDirectory(prefix="ppa-crash-") as tempdir:
        with isolated_engine(dsn, sqlite_path=Path(tempdir) / "crash.sqlite") as engine:
            report = run_acceptance(engine)
    output = json.dumps(report, indent=2, ensure_ascii=False)
    print(output)
    if args.output:
        # Consistent atomic report writing with the existing demo.
        fd, tmp = tempfile.mkstemp(prefix=".ppa-report-", dir=str(args.output.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(output + "\n")
            os.replace(tmp, args.output)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
