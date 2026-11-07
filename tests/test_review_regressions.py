"""Regression contracts for Reprovant v0.2.1 review fixes.

The pre-fix main branch violates terminal replay, SQLite FK/length limits,
and explicit worker-execution disclaimer checks. All should pass after the
companion patch. Test only against the disposable database fixture.
"""
from __future__ import annotations

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import DataError, IntegrityError

from pipeline_acceptance.guarded import process_once
from pipeline_acceptance.replay_contract import ReplayContract, Snapshot, evaluate_replay
from pipeline_acceptance.storage import (
    effects,
    get_effect_count,
    get_status,
    seed_job,
    seed_dataset,
)


# RED 1: Proposed terminal-state contract. The current implementation inserts
# an effect before determining that the job was already SUCCEEDED.
def test_succeeded_without_effect_cannot_create_a_new_effect(engine):
    seed_job(engine, "done-no-effect", status="SUCCEEDED")

    with pytest.raises(ValueError, match=r"(?i)(terminal|succeed|effect|replay)"):
        process_once(engine, "done-no-effect", "effect:late", "new")

    assert get_status(engine, "done-no-effect") == "SUCCEEDED"
    assert get_effect_count(engine, "effect:late") == 0


# RED 2: SQLite's FK checks are off without PRAGMA foreign_keys=ON.
# This must enforce the same invariant on both supported DB backends.
def test_effect_requires_an_existing_job_at_database_level(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                insert(effects).values(
                    logical_key="effect:orphan",
                    job_id="missing-job",
                    payload="not-allowed",
                )
            )
    assert get_effect_count(engine, "effect:orphan") == 0


# RED 3-4: Require consistent Python-side input limits across PostgreSQL and
# SQLite, instead of relying on dialect-specific VARCHAR enforcement.
@pytest.mark.parametrize(
    ("logical_key", "payload"),
    [("k" * 81, "ok"), ("effect:long-payload", "x" * 501)],
    ids=["logical_key_over_80", "payload_over_500"],
)
def test_process_once_rejects_oversized_inputs(engine, logical_key, payload):
    seed_job(engine, "length-guard")

    with pytest.raises(ValueError):
        process_once(engine, "length-guard", logical_key, payload)

    assert get_status(engine, "length-guard") == "PENDING"
    assert get_effect_count(engine, logical_key) == 0


# GREEN: Missing jobs must not leak even a briefly inserted effect to durable
# storage. The current transaction rollback already handles this path.
def test_missing_job_never_leaves_a_durable_effect(engine):
    with pytest.raises((ValueError, IntegrityError)):
        process_once(engine, "nonexistent", "effect:missing", "payload")
    assert get_effect_count(engine, "effect:missing") == 0


# GREEN: FAILED jobs also roll back their tentative effect insert.
def test_failed_job_never_leaves_a_durable_effect(engine):
    seed_job(engine, "failed-job", status="FAILED")
    with pytest.raises(ValueError):
        process_once(engine, "failed-job", "effect:failed", "payload")
    assert get_status(engine, "failed-job") == "FAILED"
    assert get_effect_count(engine, "effect:failed") == 0


# GREEN: An exact replay of a completed job MUST keep working after the
# proposed terminal-state correction; blocking every SUCCEEDED job is wrong.
def test_succeeded_with_existing_matching_effect_allows_exact_replay(engine):
    seed_job(engine, "already-done")
    process_once(engine, "already-done", "effect:existing", "same")
    process_once(engine, "already-done", "effect:existing", "same")
    assert get_status(engine, "already-done") == "SUCCEEDED"
    assert get_effect_count(engine, "effect:existing") == 1


# GREEN CHARACTERIZATION: not a current bug; shows the advertised v0 scope.
# Adapter dispatch returns without work, yet invariant snapshots remain valid.
def test_v0_green_only_proves_observed_invariants_not_worker_execution():
    class NoWorkAdapter:
        def __init__(self):
            self.dispatch_called = 0

        def is_disposable(self):
            return True

        def observe(self):
            return Snapshot(state="SUCCEEDED", effects={"sent": 1})

        def dispatch(self):
            self.dispatch_called += 1  # no actual queue or worker invocation

    adapter = NoWorkAdapter()
    contract = ReplayContract("noop-characterization", "SUCCEEDED", {"sent": 1})
    report = evaluate_replay(adapter, contract)
    assert adapter.dispatch_called == 1
    assert report["status"] == "GREEN"
    assert report["dispatch_completed"] is True
    assert report["worker_execution_verified"] is False
    # Therefore dispatch_completed is NOT a real-worker execution receipt.


@pytest.mark.parametrize(
    ("logical_key", "payload"),
    [("k" * 81, "ok"), ("effect:long-direct", "x" * 501)],
    ids=["raw_logical_key_over_80", "raw_payload_over_500"],
)
def test_raw_database_effect_lengths_rejected_on_both_backends(engine, logical_key, payload):
    # SQL CHECK closes SQLite's normal VARCHAR loophole, independently of the
    # Python-side guard. PostgreSQL rejects the same oversized inputs.
    seed_job(engine, "raw-length-job")
    with pytest.raises((IntegrityError, DataError)):
        with engine.begin() as conn:
            conn.execute(insert(effects).values(
                job_id="raw-length-job", logical_key=logical_key, payload=payload
            ))
    assert get_effect_count(engine, logical_key) == 0


def test_sqlite_foreign_keys_pragma_is_enabled(engine):
    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite-specific connection configuration")
    from sqlalchemy import text
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1



def test_database_rejects_overlong_job_id(engine):
    with pytest.raises((IntegrityError, DataError)):
        seed_job(engine, "j" * 81)


def test_database_rejects_overlong_dataset_value(engine):
    with pytest.raises((IntegrityError, DataError)):
        seed_dataset(engine, "slot:overlong", "x" * 501)
