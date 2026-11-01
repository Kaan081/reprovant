"""Strict JUnit-to-evidence gate: never claims PASS without all required cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

CASES = (
    "test_control_pending_can_be_confirmed",
    "test_contract_shipped_must_not_regress",
    "test_contract_confirmed_replay_emits_no_duplicate_event",
)
PIN = "c08455d626d5e1c316d932c4da0652086fb1b19e"


def evaluate(xml_path: Path, pytest_exit: int, upstream_sha: str) -> dict:
    result = {
        "experiment": "external-eventflow-contract-01",
        "upstream_repository": "juneja-varun/eventflow",
        "upstream_sha": upstream_sha,
        "expected_upstream_sha": PIN,
        "pytest_exit_code": pytest_exit,
        "evidence_scope": "External public demo on disposable PostgreSQL; not a paid buyer, production incident, or AI benchmark",
        "status": "INCONCLUSIVE",
        "cases": {},
    }
    if upstream_sha != PIN or not xml_path.exists():
        result["reason"] = "unverified_upstream_revision_or_missing_junit"
        return result
    try:
        root = ET.parse(xml_path).getroot()
        found: dict[str, str] = {}
        for case in root.iter("testcase"):
            name = case.get("name", "")
            if name not in CASES:
                continue
            if name in found:
                result["reason"] = "duplicate_test_identity"
                return result
            outcome = "PASS"
            if case.find("error") is not None:
                outcome = "ERROR"
            elif case.find("failure") is not None:
                outcome = "FAIL"
            elif case.find("skipped") is not None:
                outcome = "SKIP"
            found[name] = outcome
        result["cases"] = found
        if set(found) != set(CASES):
            result["reason"] = "required_case_missing"
        elif pytest_exit not in (0, 1):
            result["reason"] = "pytest_infrastructure_failure"
        elif found[CASES[0]] != "PASS":
            result["reason"] = "positive_control_failed"
        elif any(found[name] in ("ERROR", "SKIP") for name in CASES[1:]):
            result["reason"] = "unverified_invariant"
        elif pytest_exit == 0 and all(x == "PASS" for x in found.values()):
            result["status"] = "PASS"
        elif pytest_exit == 1 and any(found[name] == "FAIL" for name in CASES[1:]):
            result["status"] = "FAIL"
            result["reason"] = "observed_contract_violation"
        else:
            result["reason"] = "inconsistent_pytest_result"
    except (ET.ParseError, OSError, ValueError) as exc:
        result["reason"] = "invalid_junit_xml"
        result["parse_error_type"] = type(exc).__name__
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--pytest-exit", type=int, required=True)
    parser.add_argument("--upstream-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.junit, args.pytest_exit, args.upstream_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"External acceptance: {result['status']} (scope: external disposable PostgreSQL)")
    if "reason" in result:
        print(f"Reason: {result['reason']}")
    return 0 if result["status"] == "PASS" else (1 if result["status"] == "FAIL" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
