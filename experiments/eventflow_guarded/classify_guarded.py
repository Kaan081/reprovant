"""Fail-closed classification of 03B live-worker guarded experiment.

03A's original probe exits nonzero when behavior is guarded by design.
This wrapper verifies the entire positive and negative-control evidence;
it does not change the old 03A experiment or claim exactly-once delivery.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PIN = "c08455d626d5e1c316d932c4da0652086fb1b19e"


def classify(report: dict, probe_exit: str, patched_files: list[str]) -> dict:
    result = {
        "experiment": "eventflow-03b-guarded-live-worker",
        "status": "INCONCLUSIVE",
        "upstream_expected_sha": PIN,
        "upstream_revision": report.get("observation", {}).get("upstream_revision"),
        "probe_status": report.get("status"),
        "probe_exit": probe_exit,
        "changed_upstream_files": patched_files,
        "scope": "disposable real PostgreSQL+Redis+Celery worker; patched demo checkout; manual enqueue, NOT ACK loss or worker crash",
    }
    if result["upstream_revision"] != PIN or patched_files != ["orders/tasks.py"]:
        result["reason"] = "provenance_not_verified"
        return result
    if probe_exit != "2":
        result["reason"] = "unexpected_probe_exit"
        return result
    if report.get("status") == "OBSERVED_RED":
        result["status"] = "FAIL"
        result["reason"] = "guarded_patch_did_not_prevent_regression"
        return result
    if report.get("status") != "NOT_REPRODUCED" or report.get("reason") != "upstream_behaved_as_guarded":
        result["reason"] = "incomplete_or_ambiguous_probe"
        return result
    obs = report.get("observation", {})
    conditions = (
        obs.get("worker_seen") is True,
        obs.get("eager_mode") is False,
        bool(obs.get("worker_names")),
        obs.get("first_task_state") == "SUCCESS",
        obs.get("second_task_state") == "SUCCESS",
        obs.get("first_status") == "confirmed",
        obs.get("first_confirmed_events") == 1,
        obs.get("status_after_manual_reenqueue") == "shipped",
        obs.get("confirmed_events_total") == 1,
        obs.get("task_acks_late") is False,
        obs.get("first_task_id") is not None,
        obs.get("second_task_id") is not None,
        obs.get("first_task_id") != obs.get("second_task_id"),
        len(obs.get("event_log", [])) == 1,
        (obs.get("event_log") or [{}])[0].get("type") == "order.confirmed",
    )
    if not all(conditions):
        result["reason"] = "missing_positive_or_negative_control"
        return result
    result["status"] = "GUARDED_GREEN"
    result["reason"] = "terminal_state_and_event_count_preserved_on_manual_reenqueue"
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--probe-json", type=Path, required=True)
    p.add_argument("--probe-exit", required=True)
    p.add_argument("--changed-files", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        report = json.loads(args.probe_json.read_text(encoding="utf8"))
        changed_files = [x.strip() for x in args.changed_files.read_text(encoding="utf8").splitlines() if x.strip()]
        output = classify(report, args.probe_exit, changed_files)
    except (ValueError, OSError, TypeError, KeyError, IndexError) as exc:
        output = {"experiment": "eventflow-03b-guarded-live-worker", "status": "INCONCLUSIVE", "reason": "unreadable_evidence", "error_type": type(exc).__name__}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True)+"\n", encoding="utf8")
    print("EVENTFLOW 03B:", output["status"], output.get("reason", ""))
    return 0 if output["status"] == "GUARDED_GREEN" else (1 if output["status"] == "FAIL" else 2)

if __name__ == "__main__":
    raise SystemExit(main())
