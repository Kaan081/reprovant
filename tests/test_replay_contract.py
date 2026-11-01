from __future__ import annotations

import json

import pytest

from pipeline_acceptance.guarded import process_once
from pipeline_acceptance.legacy import process_with_bug, stale_running_update_with_bug
from pipeline_acceptance.replay_contract import (
    ReplayContract, Snapshot, evaluate_replay, write_evidence,
)
from pipeline_acceptance.storage import get_effect_count, get_status, seed_job


class Adapter:
    def __init__(self, state="SHIPPED", effects=None, after=None, safe=True, fail_at=None):
        self.before = Snapshot(state, effects if effects is not None else {"confirmed": 1})
        self.after = after or self.before
        self.safe = safe
        self.fail_at = fail_at
        self.invoked = 0
        self.observed = 0

    def is_disposable(self):
        if self.fail_at == "safety":
            raise RuntimeError("SECRET=abc")
        return self.safe

    def observe(self):
        self.observed += 1
        if self.fail_at == "after" and self.observed == 2:
            raise ConnectionError("postgresql://test-user:secret@example.invalid/db")
        return self.before if self.observed == 1 else self.after

    def dispatch(self):
        self.invoked += 1
        if self.fail_at == "dispatch":
            raise RuntimeError("SECRET=abc")


def spec():
    return ReplayContract("test", "SHIPPED", {"confirmed": 1})


def test_green_requires_real_dispatch_and_complete_snapshots():
    adapter = Adapter()
    result = evaluate_replay(adapter, spec())
    assert result["status"] == "GREEN"
    assert result["dispatch_completed"] is True
    assert result["before"] == {"state": "SHIPPED", "effects": {"confirmed": 1}}
    assert adapter.invoked == 1 and adapter.observed == 2
    assert result["schema_version"] == "reprovant.replay-contract.v0"


def test_duplicate_effect_red():
    result = evaluate_replay(Adapter(after=Snapshot("SHIPPED", {"confirmed": 2})), spec())
    assert result["status"] == "RED"
    assert result["failed_checks"] == ["effect:confirmed"]


def test_state_regression_red():
    result = evaluate_replay(Adapter(after=Snapshot("CONFIRMED", {"confirmed": 1})), spec())
    assert result["status"] == "RED"
    assert result["failed_checks"] == ["state_preserved"]


def test_effect_count_loss_red():
    result = evaluate_replay(Adapter(after=Snapshot("SHIPPED", {"confirmed": 0})), spec())
    assert result["status"] == "RED"


def test_precondition_fail_closed_without_dispatch():
    adapter = Adapter(state="PENDING")
    result = evaluate_replay(adapter, spec())
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "baseline_precondition_not_met"
    assert adapter.invoked == 0


def test_mismatching_baseline_count_never_dispatches():
    adapter = Adapter(effects={"confirmed": 0})
    assert evaluate_replay(adapter, spec())["status"] == "INCONCLUSIVE"
    assert adapter.invoked == 0


def test_unsafe_environment_never_dispatches():
    adapter = Adapter(safe=False)
    assert evaluate_replay(adapter, spec())["reason"] == "disposable_environment_not_attested"
    assert adapter.observed == 0 and adapter.invoked == 0


@pytest.mark.parametrize("stage", ["safety", "dispatch", "after"])
def test_adapter_failure_is_inconclusive_without_leaking_secret(stage):
    adapter = Adapter(fail_at=stage)
    report = evaluate_replay(adapter, spec())
    assert report["status"] == "INCONCLUSIVE"
    assert report["error_phase"] == ("safety_check" if stage == "safety" else "observe_after" if stage == "after" else "dispatch")
    assert "secret" not in json.dumps(report).lower()
    assert "abc" not in json.dumps(report).lower()


def test_after_missing_metric_inconclusive():
    class MissingAdapter(Adapter):
        def observe(self):
            self.observed += 1
            if self.observed == 1:
                return self.before
            return Snapshot("SHIPPED", {"unrelated": 4})
    report = evaluate_replay(MissingAdapter(), spec())
    assert report["status"] == "INCONCLUSIVE"
    assert report["reason"] == "incomplete_post_replay_observation"


def test_invalid_observer_return_inconclusive():
    class BadAdapter(Adapter):
        def observe(self):
            return {"state": "SHIPPED", "effects": {"confirmed": 1}}
    assert evaluate_replay(BadAdapter(), spec())["reason"] == "incomplete_pre_replay_observation"


@pytest.mark.parametrize("value", [-1, 1.0, True, "1", None])
def test_invalid_counts_rejected(value):
    with pytest.raises(ValueError):
        Snapshot("SHIPPED", {"confirmed": value})


def test_invalid_max_growth_rejected():
    with pytest.raises(ValueError):
        ReplayContract("name", "SHIPPED", {"confirmed": 1}, {"unknown": 1})


def test_allowed_growth_is_explicit():
    contract = ReplayContract("growth", "SHIPPED", {"confirmed": 1}, {"confirmed": 1})
    result = evaluate_replay(Adapter(after=Snapshot("SHIPPED", {"confirmed": 2})), contract)
    assert result["status"] == "GREEN"


def test_write_atomic_evidence(tmp_path):
    result = evaluate_replay(Adapter(), spec())
    path = tmp_path / "out" / "proof.json"
    write_evidence(path, result)
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "GREEN"
    assert sorted(x.name for x in path.parent.iterdir()) == ["proof.json"]


def test_metric_whitelist_does_not_export_extra_adapter_data():
    a = Adapter(effects={"confirmed": 1, "private_user_id": 123})
    report = evaluate_replay(a, spec())
    assert report["status"] == "GREEN"
    assert "private_user_id" not in json.dumps(report)


def test_real_disposable_sqlite_guarded_green(engine):
    seed_job(engine, "contract-j1")
    process_once(engine, "contract-j1", "c:1", "ok")

    class SqlAdapter:
        def is_disposable(self): return True  # engine fixture owns local DB
        def observe(self):
            return Snapshot(get_status(engine, "contract-j1"),
                            {"effects": get_effect_count(engine, "c:1")})
        def dispatch(self):
            process_once(engine, "contract-j1", "c:1", "ok")

    result = evaluate_replay(SqlAdapter(), ReplayContract("replay", "SUCCEEDED", {"effects": 1}))
    assert result["status"] == "GREEN"


def test_real_disposable_sqlite_legacy_duplicate_red(engine):
    seed_job(engine, "contract-j1")
    process_with_bug(engine, "contract-j1", "c:1", "ok")

    class SqlAdapter:
        def is_disposable(self): return True  # engine fixture owns local DB
        def observe(self):
            return Snapshot(get_status(engine, "contract-j1"),
                            {"effects": get_effect_count(engine, "c:1", legacy=True)})
        def dispatch(self):
            process_with_bug(engine, "contract-j1", "c:1", "ok")

    result = evaluate_replay(SqlAdapter(), ReplayContract("legacy", "SUCCEEDED", {"effects": 1}))
    assert result["status"] == "RED"


def test_real_disposable_sqlite_stale_writer_red(engine):
    seed_job(engine, "contract-j1", "SUCCEEDED")

    class SqlAdapter:
        def is_disposable(self): return True  # engine fixture owns local DB
        def observe(self):
            return Snapshot(get_status(engine, "contract-j1"), {"effects": 0})
        def dispatch(self):
            stale_running_update_with_bug(engine, "contract-j1")

    result = evaluate_replay(SqlAdapter(), ReplayContract("legacy-state", "SUCCEEDED", {"effects": 0}))
    assert result["status"] == "RED"
