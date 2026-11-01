from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from pipeline_acceptance.guarded import accept_validated_dataset, process_once, try_mark_running
from pipeline_acceptance.legacy import AckLostAfterCommit
from pipeline_acceptance.storage import (
    get_dataset, get_effect_count, get_status, seed_dataset, seed_job,
)


def test_control_success(engine):
    seed_job(engine, "j1")
    process_once(engine, "j1", "email:123", "sent")
    assert get_effect_count(engine, "email:123") == 1
    assert get_status(engine, "j1") == "SUCCEEDED"


def test_crash_after_commit_before_ack_then_replay_does_not_duplicate(engine):
    seed_job(engine, "j1")
    with pytest.raises(AckLostAfterCommit):
        process_once(engine, "j1", "invoice:55", "paid", crash_after_commit=True)
    assert get_effect_count(engine, "invoice:55") == 1
    process_once(engine, "j1", "invoice:55", "paid")  # redelivery of same work item
    assert get_effect_count(engine, "invoice:55") == 1
    assert get_status(engine, "j1") == "SUCCEEDED"


def test_stale_worker_cannot_downgrade_terminal_success(engine):
    seed_job(engine, "j1", "RUNNING")
    process_once(engine, "j1", "job:1", "result")
    assert try_mark_running(engine, "j1") is False
    assert get_status(engine, "j1") == "SUCCEEDED"


def test_validation_failure_does_not_overwrite_prior_good_data(engine):
    seed_job(engine, "j1")
    seed_dataset(engine, "daily-sales", "good-v1")
    with pytest.raises(ValueError, match="Validation failed"):
        accept_validated_dataset(engine, "j1", "daily-sales", "bad-empty", valid=False)
    assert get_dataset(engine, "daily-sales") == ("good-v1", 1)
    assert get_status(engine, "j1") == "PENDING"


def test_valid_data_is_committed_with_success_state(engine):
    seed_job(engine, "j1")
    seed_dataset(engine, "daily-sales", "old")
    accept_validated_dataset(engine, "j1", "daily-sales", "good-v2", valid=True)
    assert get_dataset(engine, "daily-sales") == ("good-v2", 2)
    assert get_status(engine, "j1") == "SUCCEEDED"


def test_idempotency_key_conflict_fails_closed(engine):
    seed_job(engine, "j1")
    seed_job(engine, "j2")
    process_once(engine, "j1", "payment:45", "100")
    with pytest.raises(ValueError, match="Idempotency-key collision"):
        process_once(engine, "j2", "payment:45", "200")
    assert get_effect_count(engine, "payment:45") == 1
    assert get_status(engine, "j2") == "PENDING"


def test_same_job_replay_with_new_key_fails_closed(engine):
    seed_job(engine, "j1")
    process_once(engine, "j1", "notification:1", "sent")
    with pytest.raises(ValueError, match="Idempotency-key collision"):
        process_once(engine, "j1", "notification:different-key", "sent")
    assert get_effect_count(engine, "notification:different-key") == 0
    assert get_status(engine, "j1") == "SUCCEEDED"


def test_try_running_from_retry_only(engine):
    seed_job(engine, "j1", "RETRY")
    assert try_mark_running(engine, "j1") is True
    assert try_mark_running(engine, "j1") is False
    assert get_status(engine, "j1") == "RUNNING"


def test_concurrent_duplicate_delivery_postgres_only(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL integration concurrency test requires PIPELINE_TEST_DSN")
    seed_job(engine, "j1")
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(process_once, engine, "j1", "invoice:race", "done") for _ in range(2)]
        for f in tasks:
            f.result(timeout=15)
    assert get_effect_count(engine, "invoice:race") == 1
    assert get_status(engine, "j1") == "SUCCEEDED"
