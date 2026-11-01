"""Fail-closed ordinary-pytest JUnit assessment; not a product adapter."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

UPSTREAM_PIN = "28a65c42a9bdbcc6d2ed08038311ae22e9d66d11"
EXPECTED = (
    "test_control_pipeline_persists_successful_run",
    "test_replay_does_not_change_final_business_rows",
    "test_bad_inputs_are_rejected_and_audited",
    "test_atomic_clean_rejected_load_rolls_back_on_fk_error",
)


def classify(xml_path: Path, pytest_exit: str, revision: str) -> dict:
    result = {
        "experiment": "external-etl-pytest-baseline-02A",
        "method": "pytest-only",
        "upstream_revision": revision,
        "expected_revision": UPSTREAM_PIN,
        "pytest_exit": pytest_exit,
        "status": "INCONCLUSIVE",
        "cases": {},
        "scope": "disposable PostgreSQL; educational open-source upstream; not a customer incident",
    }
    if revision != UPSTREAM_PIN or not xml_path.is_file():
        result["reason"] = "missing_junit_or_revision_mismatch"
        return result
    try:
        found = {}
        for case in ET.parse(xml_path).getroot().iter("testcase"):
            name = case.attrib.get("name", "")
            if name not in EXPECTED:
                continue
            if name in found:
                result["reason"] = "duplicate_testcase"
                return result
            found[name] = (
                "ERROR" if case.find("error") is not None else
                "FAIL" if case.find("failure") is not None else
                "SKIP" if case.find("skipped") is not None else "PASS"
            )
        result["cases"] = found
        if set(found) != set(EXPECTED):
            result["reason"] = "missing_required_case"
        elif pytest_exit not in ("0", "1"):
            result["reason"] = "pytest_infrastructure_error"
        elif found[EXPECTED[0]] != "PASS":
            result["reason"] = "positive_control_failed"
        elif any(v in ("SKIP", "ERROR") for v in found.values()):
            result["reason"] = "skipped_or_error_case"
        elif pytest_exit == "0" and all(v == "PASS" for v in found.values()):
            result["status"] = "PASS"
        elif pytest_exit == "1" and any(v == "FAIL" for v in found.values()):
            result["status"] = "FAIL"
            result["reason"] = "observed_assertion_failure"
        else:
            result["reason"] = "inconsistent_pytest_result"
    except (ET.ParseError, OSError):
        result["reason"] = "unreadable_junit"
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--junit", type=Path, required=True)
    p.add_argument("--pytest-exit", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = classify(args.junit, args.pytest_exit, args.revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("ETL pytest baseline:", result["status"], result.get("reason", ""))
    return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
