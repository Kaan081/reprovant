"""05A pure tests: not proof of external Flask/Celery worker execution."""
from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from experiments.portability_05a import scenario, verdict
from pipeline_acceptance.replay_contract import ReplayContract, Snapshot, evaluate_replay


def att():
    return {"worker_seen": True, "eager_mode": False,
            "first_task_state": "SUCCESS", "second_task_state": "SUCCESS",
            "distinct_task_ids": True}


def sample():
    return {"source_pin": scenario.PIN, "before": verdict.PRE,
            "after": verdict.POST, "worker": att()}


def junit(marker="INVARIANT_EXTRA_ATTEMPT", *, invalid=False, skipped=False, error=False):
    root = ET.Element("testsuite")
    ET.SubElement(root, "testcase", name="test_first_dispatch_succeeded")
    second = ET.SubElement(root, "testcase", name="test_replay_preserves_attempt_count")
    child = ET.SubElement(second, "error" if error else "failure", message=marker)
    if skipped:
        ET.SubElement(second, "skipped")
    if invalid:
        ET.SubElement(root, "testcase", name="test_extra")
    return ET.tostring(root, encoding="unicode")


def test_pytest_expected_red():
    assert verdict.plain_pytest(sample(), junit(), 1)["status"] == "VERIFIED_PYTEST_RED"


@pytest.mark.parametrize("xml,exit_code", [
    (junit(), 0), (junit(), 2), (junit("OTHER_FAILURE"), 1),
    (junit(error=True), 1), (junit(skipped=True), 1),
    (junit(invalid=True), 1), ("invalid xml", 1),
])
def test_pytest_unexpected_failure_inconclusive(xml, exit_code):
    assert verdict.plain_pytest(sample(), xml, exit_code)["status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("field,value", [
    ("worker_seen", False), ("eager_mode", True),
    ("first_task_state", "FAILURE"), ("second_task_state", "FAILURE"),
    ("distinct_task_ids", False),
])
def test_missing_attestation_inconclusive(field, value):
    snap = sample()
    snap["worker"][field] = value
    assert verdict.plain_pytest(snap, junit(), 1)["status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("field,value", [
    ("source_pin", "wrong"),
    ("before", {"state": "success", "attempts": 0}),
    ("after", {"state": "success", "attempts": 1}),
])
def test_wrong_snapshots_inconclusive(field, value):
    snap = sample()
    snap[field] = value
    assert verdict.plain_pytest(snap, junit(), 1)["status"] == "INCONCLUSIVE"


class FakeAdapter:
    def __init__(self, *, grow=True, disposable=True):
        self.n = 1
        self.grow = grow
        self.disposable = disposable
        self.dispatched = False

    def is_disposable(self):
        return self.disposable

    def observe(self):
        return Snapshot("success", {"attempts": self.n})

    def dispatch(self):
        self.dispatched = True
        if self.grow:
            self.n += 1


def synthetic_reprovant(grow=True, disposable=True):
    report = evaluate_replay(FakeAdapter(grow=grow, disposable=disposable),
                             ReplayContract("job-no-extra-processing", "success", {"attempts": 1}))
    return {"source_pin": scenario.PIN, "worker": att(), "contract_report": report}


def test_reprovant_synthetic_negative_control():
    r = verdict.reprovant(synthetic_reprovant())
    assert r["status"] == "VERIFIED_REPROVANT_RED"


def test_reprovant_synthetic_green_is_not_expected_red():
    assert verdict.reprovant(synthetic_reprovant(grow=False))["status"] == "INCONCLUSIVE"


def test_reprovant_missing_disposable_attestation_is_inconclusive():
    assert verdict.reprovant(synthetic_reprovant(disposable=False))["status"] == "INCONCLUSIVE"


def test_parity_requires_both_methods():
    p = verdict.plain_pytest(sample(), junit(), 1)
    r = verdict.reprovant(synthetic_reprovant())
    assert verdict.parity(p, r)["status"] == "VERIFIED_SECOND_APP_PARITY"
    assert verdict.parity(p, {})["status"] == "INCONCLUSIVE"
    assert verdict.parity({}, r)["status"] == "INCONCLUSIVE"


def test_parity_wrong_source_inconclusive():
    p = verdict.plain_pytest(sample(), junit(), 1)
    r = verdict.reprovant(synthetic_reprovant())
    r["source_pin"] = "wrong"
    assert verdict.parity(p, r)["status"] == "INCONCLUSIVE"


def test_disposable_guard_requires_exact_env(monkeypatch):
    monkeypatch.delenv("PPA_PORTABILITY_DISPOSABLE", raising=False)
    with pytest.raises(RuntimeError, match="Refusing non-disposable"):
        scenario.assert_disposable()


def test_no_external_source_checked_into_reprovant():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "external-queue-app").exists()
