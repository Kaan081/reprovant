"""INTENTIONALLY FAILING test cases. Run explicitly with pytest tests/legacy_red_cases.py.

These cases demonstrate why the pre-fix implementation violates invariants.
"""
import pytest

from pipeline_acceptance.legacy import (
    AckLostAfterCommit, process_with_bug, stale_running_update_with_bug, update_dataset_with_bug,
)
from pipeline_acceptance.storage import (
    get_dataset, get_effect_count, get_status, seed_dataset, seed_job,
)


def test_legacy_replay_must_not_duplicate(engine):
    seed_job(engine, "legacy1")
    with pytest.raises(AckLostAfterCommit):
        process_with_bug(engine, "legacy1", "invoice:1", "charged", crash_after_commit=True)
    process_with_bug(engine, "legacy1", "invoice:1", "charged")
    assert get_effect_count(engine, "invoice:1", legacy=True) == 1


def test_legacy_stale_update_must_not_regress_success(engine):
    seed_job(engine, "legacy2", "RUNNING")
    process_with_bug(engine, "legacy2", "order:2", "fulfilled")
    stale_running_update_with_bug(engine, "legacy2")
    assert get_status(engine, "legacy2") == "SUCCEEDED"


def test_legacy_invalid_data_must_not_replace_good(engine):
    seed_job(engine, "legacy3")
    seed_dataset(engine, "daily", "good-v1")
    with pytest.raises(ValueError, match="Validation failed"):
        update_dataset_with_bug(engine, "legacy3", "daily", "invalid", valid=False)
    assert get_dataset(engine, "daily") == ("good-v1", 1)
