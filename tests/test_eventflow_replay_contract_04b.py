"""04B local pure-unit / fake-worker tests; NOT evidence of a live external stack."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from pipeline_acceptance.replay_contract import ReplayContract, Snapshot, evaluate_replay


PATH = Path(__file__).resolve().parents[1] / "experiments/eventflow_replay_contract/run_contract.py"
SPEC = importlib.util.spec_from_file_location("eventflow_04b_unit", PATH)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def valid_checks():
    return {"worker_seen": True, "worker_names": ["celery@isolated"],
            "eager_mode": False, "subscription_confirmed": True,
            "first_task_state": "SUCCESS", "second_task_state": "SUCCESS",
            "first_status": "confirmed", "first_confirmed_events": 1,
            "shipped_transition_rows": 1, "distinct_task_ids": True,
            "task_acks_late": False, "task_reject_on_worker_lost": False}


def fake_contract(after_state, effects):
    class Adapter:
        def is_disposable(self): return True
        def __init__(self): self.calls = 0
        def observe(self):
            self.calls += 1
            return Snapshot("shipped", {"order_confirmed": 1}) if self.calls == 1 else Snapshot(after_state, {"order_confirmed": effects})
        def dispatch(self): pass
    return evaluate_replay(Adapter(), ReplayContract("eventflow-no-regression", "shipped", {"order_confirmed": 1}))


def test_original_control_red_expected():
    result = m.classify_run("upstream", m.PIN, [], fake_contract("confirmed", 2), valid_checks())
    assert result["status"] == "VERIFIED_RED_CONTROL"
    assert result["contract_report"]["status"] == "RED"


def test_guarded_green_expected():
    result = m.classify_run("guarded", m.PIN, ["orders/tasks.py"], fake_contract("shipped", 1), valid_checks())
    assert result["status"] == "VERIFIED_GUARDED_GREEN"
    assert result["contract_report"]["status"] == "GREEN"


@pytest.mark.parametrize("mode,changed", [("upstream", ["orders/tasks.py"]), ("guarded", []), ("guarded", ["other.py"])])
def test_wrong_source_patch_inconclusive(mode, changed):
    assert m.classify_run(mode, m.PIN, changed, fake_contract("shipped", 1), valid_checks())["reason"] == "source_provenance_mismatch"


def test_wrong_sha_inconclusive():
    assert m.classify_run("guarded", "wrong", ["orders/tasks.py"], fake_contract("shipped", 1), valid_checks())["status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("field,value", [("worker_seen", False), ("eager_mode", True),
                                        ("subscription_confirmed", False), ("first_task_state", "FAILURE"),
                                        ("first_confirmed_events", 0), ("second_task_state", "PENDING"),
                                        ("distinct_task_ids", False), ("worker_names", [])])
def test_missing_worker_attestation_inconclusive(field, value):
    checks = valid_checks()
    checks[field] = value
    assert m.classify_run("guarded", m.PIN, ["orders/tasks.py"], fake_contract("shipped", 1), checks)["status"] == "INCONCLUSIVE"


def test_guarded_unexpected_red_is_not_pass():
    r = m.classify_run("guarded", m.PIN, ["orders/tasks.py"], fake_contract("confirmed", 2), valid_checks())
    assert r["status"] == "INCONCLUSIVE"  # inconsistent with protected-source attestation


def test_original_unexpected_green_is_not_pass():
    r = m.classify_run("upstream", m.PIN, [], fake_contract("shipped", 1), valid_checks())
    assert r["status"] == "INCONCLUSIVE"  # unexpected control shape does not satisfy checks


def test_no_dispatch_is_inconclusive():
    r = fake_contract("shipped", 1)
    r["dispatch_completed"] = False
    assert m.classify_run("guarded", m.PIN, ["orders/tasks.py"], r, valid_checks())["status"] == "INCONCLUSIVE"


class FakeOrder:
    pk = 101
    status = "shipped"
    def refresh_from_db(self): pass


class FakeAsyncResult:
    id = "second-task"
    state = "SUCCESS"
    def get(self, *, timeout, propagate):
        assert timeout == 40 and propagate is True


class FakeTask:
    def apply_async(self, *, args):
        assert args == [101]
        return FakeAsyncResult()


class FakeProbe:
    @staticmethod
    def assert_disposable(): pass
    @staticmethod
    def read_upstream_revision(): return m.PIN
    @staticmethod
    def gather_events(pubsub, order_id, seconds):
        assert order_id == 101 and seconds == 2.0
        return [{"type": "order.confirmed"}]


def test_fake_worker_adapter_negative_control():
    info = valid_checks()
    adapter = m.EventflowAdapter(FakeOrder(), FakeTask(), object(), FakeProbe(), info, "first-task")
    report = evaluate_replay(adapter, ReplayContract("fake", "shipped", {"order_confirmed": 1}))
    assert report["status"] == "RED"
    assert info["distinct_task_ids"] is True
    assert info["second_task_state"] == "SUCCESS"


def test_fake_worker_mismatched_revision_is_inconclusive():
    class WrongProbe(FakeProbe):
        @staticmethod
        def read_upstream_revision(): return "wrong"
    adapter = m.EventflowAdapter(FakeOrder(), FakeTask(), object(), WrongProbe(), {}, "first-task")
    report = evaluate_replay(adapter, ReplayContract("fake", "shipped", {"order_confirmed": 1}))
    assert report["reason"] == "disposable_environment_not_attested"


def test_fake_worker_missing_result_does_not_green():
    class BadTask(FakeTask):
        def apply_async(self, *, args):
            class Bad(FakeAsyncResult):
                state = "PENDING"
            return Bad()
    info = valid_checks()
    adapter = m.EventflowAdapter(FakeOrder(), BadTask(), object(), FakeProbe(), info, "first-task")
    report = evaluate_replay(adapter, ReplayContract("fake", "shipped", {"order_confirmed": 1}))
    assert report["status"] == "INCONCLUSIVE"
    assert report["error_phase"] == "dispatch"
