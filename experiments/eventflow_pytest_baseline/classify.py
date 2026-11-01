"""Classify ordinary pytest JUnit and independent live-worker snapshot, fail-closed.

An expected RED is two particular *assertion failures*, not two arbitrary
pytest failures. Fixture errors, missing evidence, skipped/extra tests are never
accepted. This classifier imports no Reprovant verification engine.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

PIN = "c08455d626d5e1c316d932c4da0652086fb1b19e"
TEST_MARKERS = {
    "test_terminal_state_preserved": "INVARIANT_STATE_REGRESSION",
    "test_no_duplicate_confirmation": "INVARIANT_DUPLICATE_CONFIRMATION",
}


def expected_changes(mode: str) -> list[str]:
    if mode == "upstream":
        return []
    if mode == "guarded":
        return ["orders/tasks.py"]
    raise ValueError("unsupported mode")


def parse_junit(xml: str) -> dict[str, str]:
    root = ET.fromstring(xml)
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
        if len(suites) != 1:
            raise ValueError("exactly one pytest suite required")
        root = suites[0]
    if root.tag != "testsuite":
        raise ValueError("JUnit test suite missing")
    cases = root.findall("testcase")
    if len(cases) != len(TEST_MARKERS):
        raise ValueError("expected exactly two tests")
    outcomes: dict[str, str] = {}
    for case in cases:
        name = case.attrib.get("name")
        if name not in TEST_MARKERS or name in outcomes:
            raise ValueError("unknown or repeated test case")
        if case.find("error") is not None or case.find("skipped") is not None:
            raise ValueError("error or skipped test cannot prove outcome")
        failure = case.find("failure")
        if failure is None:
            outcomes[name] = "PASS"
        else:
            marker = TEST_MARKERS[name]
            content = (failure.attrib.get("message", "") + "\n" + (failure.text or ""))
            if marker not in content:
                raise ValueError("failure is not the expected invariant assertion")
            outcomes[name] = "INVARIANT_FAILED"
    return outcomes


def classify(mode: str, changed_files: list[str], snapshot: dict, outcomes: dict[str, str], pytest_exit: int) -> dict:
    result = {"experiment": "eventflow-04c-plain-pytest-baseline", "mode": mode,
              "status": "INCONCLUSIVE", "reason": "missing_or_mismatched_evidence",
              "method": "plain_pytest",
              "scope": "one manual second dispatch in disposable live worker; not ACK-loss, not production guarantee"}
    if changed_files != expected_changes(mode):
        result["reason"] = "source_diff_mismatch"
        return result
    required = (
        pytest_exit == (1 if mode == "upstream" else 0),
        snapshot.get("source_pin") == PIN,
        snapshot.get("worker_seen") is True,
        snapshot.get("eager_mode") is False,
        snapshot.get("subscription_confirmed") is True,
        snapshot.get("task_acks_late") is False,
        snapshot.get("task_reject_on_worker_lost") is False,
        snapshot.get("first_task_state") == "SUCCESS",
        snapshot.get("second_task_state") == "SUCCESS",
        snapshot.get("distinct_task_ids") is True,
        snapshot.get("before") == {"state": "shipped", "order_confirmed": 1},
        set(outcomes) == set(TEST_MARKERS),
    )
    if not all(required):
        return result
    result.update(source_pin=PIN, changed_upstream_files=changed_files,
                  before=snapshot["before"], after=snapshot.get("after"))
    if mode == "upstream":
        if (snapshot.get("after") == {"state": "confirmed", "order_confirmed": 2} and
            all(outcomes[n] == "INVARIANT_FAILED" for n in TEST_MARKERS)):
            result.update(status="VERIFIED_PYTEST_RED", reason="both_invariants_detected")
    elif (snapshot.get("after") == {"state": "shipped", "order_confirmed": 1} and
          all(outcomes[n] == "PASS" for n in TEST_MARKERS)):
        result.update(status="VERIFIED_PYTEST_GREEN", reason="both_invariants_preserved")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["upstream", "guarded"])
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--pytest-exit", type=int, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--changed-files", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        outcomes = parse_junit(args.junit.read_text(encoding="utf-8"))
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        changed = [line.strip() for line in args.changed_files.read_text(encoding="utf-8").splitlines() if line.strip()]
        report = classify(args.mode, changed, snapshot, outcomes, args.pytest_exit)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, ET.ParseError) as exc:
        report = {"experiment": "eventflow-04c-plain-pytest-baseline", "mode": args.mode,
                  "status": "INCONCLUSIVE", "reason": "invalid_evidence", "error_type": type(exc).__name__}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("EVENTFLOW 04C PYTEST:", report["status"], report["reason"])
    return 0 if report["status"] == ("VERIFIED_PYTEST_RED" if args.mode == "upstream" else "VERIFIED_PYTEST_GREEN") else 2


if __name__ == "__main__":
    raise SystemExit(main())
