"""Pure unit tests: NOT live PostgreSQL/Celery/Redis evidence."""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def import_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = import_path("pytest_baseline_04c", ROOT / "experiments/eventflow_pytest_baseline/classify.py")
comparison = import_path("pytest_compare_04c", ROOT / "experiments/eventflow_pytest_baseline/compare.py")
live = import_path("pytest_live_fixture_04c", ROOT / "experiments/eventflow_pytest_baseline/test_live.py")


def junit(state_failure=False, event_failure=False, *, extra=False, error=False, skipped=False, bogus=False):
    suite = ET.Element("testsuite")
    for name, marker, failed in (
        ("test_terminal_state_preserved", "INVARIANT_STATE_REGRESSION", state_failure),
        ("test_no_duplicate_confirmation", "INVARIANT_DUPLICATE_CONFIRMATION", event_failure),
    ):
        case = ET.SubElement(suite, "testcase", name=name)
        if failed:
            ET.SubElement(case, "failure", message="Failed: " + ("OTHER_REASON" if bogus else marker))
        if error:
            ET.SubElement(case, "error", message="setup failed")
        if skipped:
            ET.SubElement(case, "skipped")
    if extra:
        ET.SubElement(suite, "testcase", name="test_other")
    return ET.tostring(suite, encoding="unicode")


def snapshot(mode):
    return {"source_pin": baseline.PIN, "worker_seen": True, "eager_mode": False,
            "subscription_confirmed": True, "task_acks_late": False,
            "task_reject_on_worker_lost": False, "first_task_state": "SUCCESS",
            "second_task_state": "SUCCESS", "distinct_task_ids": True,
            "before": {"state": "shipped", "order_confirmed": 1},
            "after": {"state": "confirmed", "order_confirmed": 2} if mode == "upstream"
                     else {"state": "shipped", "order_confirmed": 1}}


def outcome(state_fail=False, event_fail=False):
    return baseline.parse_junit(junit(state_fail, event_fail))


def test_plain_pytest_catches_two_upstream_invariants():
    result = baseline.classify("upstream", [], snapshot("upstream"), outcome(True, True), 1)
    assert result["status"] == "VERIFIED_PYTEST_RED"
    assert result["before"] == {"state": "shipped", "order_confirmed": 1}


def test_plain_pytest_passes_guarded_control():
    result = baseline.classify("guarded", ["orders/tasks.py"], snapshot("guarded"), outcome(), 0)
    assert result["status"] == "VERIFIED_PYTEST_GREEN"


@pytest.mark.parametrize("bad_xml", [
    junit(True, True, bogus=True), junit(True, True, error=True),
    junit(False, False, skipped=True), junit(extra=True),
    "<notjunit/>", "not xml", "<testsuite><testcase name='test_terminal_state_preserved'/></testsuite>",
])
def test_invalid_junit_not_accepted(bad_xml):
    with pytest.raises((ValueError, ET.ParseError)):
        baseline.parse_junit(bad_xml)


@pytest.mark.parametrize("mutation", [
    {"worker_seen": False}, {"eager_mode": True}, {"subscription_confirmed": False},
    {"task_acks_late": True}, {"task_reject_on_worker_lost": True},
    {"first_task_state": "PENDING"}, {"second_task_state": "FAILURE"},
    {"distinct_task_ids": False}, {"source_pin": "wrong"},
    {"before": {"state": "shipped", "order_confirmed": 0}},
    {"after": {"state": "confirmed", "order_confirmed": 1}},
])
def test_incomplete_or_mismatched_upstream_evidence_does_not_pass(mutation):
    obs = snapshot("upstream")
    obs.update(mutation)
    r = baseline.classify("upstream", [], obs, outcome(True, True), 1)
    assert r["status"] == "INCONCLUSIVE"


def test_wrong_patched_files_rejected():
    result = baseline.classify("guarded", [], snapshot("guarded"), outcome(), 0)
    assert result["reason"] == "source_diff_mismatch"


@pytest.mark.parametrize("mode,pytest_exit", [("upstream", 0), ("guarded", 1), ("upstream", 2), ("guarded", 2)])
def test_wrong_pytest_exit_code_fails_closed(mode, pytest_exit):
    changed = [] if mode == "upstream" else ["orders/tasks.py"]
    outcomes = outcome(mode == "upstream", mode == "upstream")
    result = baseline.classify(mode, changed, snapshot(mode), outcomes, pytest_exit)
    assert result["status"] == "INCONCLUSIVE"


def report(mode, method):
    status = comparison.EXPECTED[(mode, method)]
    before = {"state": "shipped", "order_confirmed": 1}
    after = {"state": "confirmed", "order_confirmed": 2} if mode == "upstream" else {"state": "shipped", "order_confirmed": 1}
    common = {"source_pin": comparison.PIN, "mode": mode, "status": status,
              "changed_upstream_files": [] if mode == "upstream" else ["orders/tasks.py"]}
    if method == "pytest":
        return {**common, "before": before, "after": after}
    return {**common, "contract_report": {
        "before": {"state": before["state"], "effects": {"order_confirmed": before["order_confirmed"]}},
        "after": {"state": after["state"], "effects": {"order_confirmed": after["order_confirmed"]}},
    }}


def reports():
    return {(mode, method): report(mode, method) for mode, method in comparison.EXPECTED}


def test_four_arms_parity_but_no_claim_of_product_advantage():
    result = comparison.compare(reports())
    assert result["status"] == "VERIFIED_PARITY"
    assert result["developer_time"] == "NOT_MEASURED"
    assert result["adapter_portability"] == "NOT_MEASURED"
    assert result["runtime_speed_advantage"] == "NOT_ESTABLISHED"


def test_missing_arm_inconclusive():
    r = reports()
    del r[("guarded", "reprovant")]
    assert comparison.compare(r)["status"] == "INCONCLUSIVE"


def test_same_status_but_wrong_observation_is_not_parity():
    r = reports()
    r[("guarded", "pytest")]["after"]["order_confirmed"] = 2
    assert comparison.compare(r)["status"] == "INCONCLUSIVE"


def test_same_status_but_wrong_source_is_not_parity():
    r = reports()
    r[("upstream", "reprovant")]["source_pin"] = "wrong"
    assert comparison.compare(r)["status"] == "INCONCLUSIVE"


def test_live_fixture_unblocks_db_only_around_disposable_exercise(monkeypatch):
    """Regression for CI: pytest-django blocks ORM by default."""
    events = []

    class FakeBlocker:
        @contextmanager
        def unblock(self):
            events.append("unblock")
            try:
                yield
            finally:
                events.append("restore")

    def fake_exercise():
        events.append("exercise")
        return {"finished": True}

    monkeypatch.setattr(live, "_exercise_live", fake_exercise)
    assert live.observed.__wrapped__(FakeBlocker()) == {"finished": True}
    assert events == ["unblock", "exercise", "restore"]
