"""05A fail-closed classifiers for the two real-worker methods."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from experiments.portability_05a.scenario import PIN

PRE = {"state": "success", "attempts": 1}
POST = {"state": "success", "attempts": 2}


def attested(att: dict) -> bool:
    return (att.get("worker_seen") is True
            and att.get("eager_mode") is False
            and att.get("first_task_state") == "SUCCESS"
            and att.get("second_task_state") == "SUCCESS"
            and att.get("distinct_task_ids") is True)


def plain_pytest(snapshot: dict, xml: str, exit_code: int) -> dict:
    result = {"method": "pytest", "status": "INCONCLUSIVE"}
    try:
        root = ET.fromstring(xml)
        if root.tag == "testsuites":
            suites = root.findall("testsuite")
            if len(suites) != 1:
                return result
            root = suites[0]
        if root.tag != "testsuite":
            return result
        cases = root.findall("testcase")
        if len(cases) != 2 or exit_code != 1:
            return result
        by_name = {c.attrib.get("name"): c for c in cases}
        if len(by_name) != 2 or set(by_name) != {
            "test_first_dispatch_succeeded", "test_replay_preserves_attempt_count"
        }:
            return result
        first = by_name["test_first_dispatch_succeeded"]
        repeat = by_name["test_replay_preserves_attempt_count"]
        if (len(first) != 0 or len(repeat) != 1 or repeat[0].tag != "failure"):
            return result
        failure = repeat[0]
        content = (failure.attrib.get("message", "") + "\n" + (failure.text or ""))
        if "INVARIANT_EXTRA_ATTEMPT" not in content:
            return result
        if (snapshot.get("source_pin") != PIN or snapshot.get("before") != PRE
                or snapshot.get("after") != POST
                or not attested(snapshot.get("worker") or {})):
            return result
        result.update(status="VERIFIED_PYTEST_RED", source_pin=PIN,
                      before=PRE, after=POST)
    except (TypeError, ValueError, ET.ParseError, AttributeError, KeyError):
        pass
    return result


def reprovant(report: dict) -> dict:
    result = {"method": "reprovant", "status": "INCONCLUSIVE"}
    replay = report.get("contract_report") or {}
    if (report.get("source_pin") == PIN
            and attested(report.get("worker") or {})
            and replay.get("dispatch_completed") is True
            and replay.get("status") == "RED"
            and replay.get("failed_checks") == ["effect:attempts"]
            and replay.get("checks") == {"state_preserved": True, "effect:attempts": False}
            and replay.get("before") == {"state": "success", "effects": {"attempts": 1}}
            and replay.get("after") == {"state": "success", "effects": {"attempts": 2}}):
        result.update(status="VERIFIED_REPROVANT_RED", source_pin=PIN,
                      before=PRE, after=POST)
    return result


def parity(first: dict, second: dict) -> dict:
    result = {"status": "INCONCLUSIVE", "reason": "missing_or_invalid_evidence",
              "developer_effort": "NOT_MEASURED", "market_demand": "NOT_ESTABLISHED"}
    if (first.get("status") == "VERIFIED_PYTEST_RED"
            and second.get("status") == "VERIFIED_REPROVANT_RED"
            and first.get("source_pin") == second.get("source_pin") == PIN
            and first.get("before") == second.get("before") == PRE
            and first.get("after") == second.get("after") == POST):
        result.update(status="VERIFIED_SECOND_APP_PARITY",
                      reason="both_methods_detect_extra_processing_attempt")
    return result


def save(path: Path, report: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
