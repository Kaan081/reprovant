"""Independent pytest baseline for pinned upstream API->PostgreSQL ETL project.

Runs ONLY against a disposable PostgreSQL database created by our manual CI.
These checks test public business invariants; no upstream source modification.
"""
import os

import psycopg2
import pytest

from src.load.clean_rejected_loader import load_clean_and_rejected_records
from src.load.staging_loader import load_raw_users
from src.pipeline import run_users_pipeline
from src.utils.db import get_db_cursor
from src.utils.logger import start_run_log
from src.utils.run_id import generate_run_id


USER = {
    "id": 1,
    "name": "Original Test User",
    "username": "test_user",
    "email": "one@example.com",
    "phone": "123-456",
    "website": "example.invalid",
    "company": {"name": "Baseline Test Corp"},
}
CASES = (
    "test_control_pipeline_persists_successful_run",
    "test_replay_does_not_change_final_business_rows",
    "test_bad_inputs_are_rejected_and_audited",
    "test_atomic_clean_rejected_load_rolls_back_on_fk_error",
)


def sql_one(query, params=()):
    with get_db_cursor() as (_, cursor):
        cursor.execute(query, params)
        return cursor.fetchone()[0]


@pytest.fixture(autouse=True)
def disposable_db_guard(monkeypatch):
    """Fail closed instead of truncating a developer/production database."""
    if os.getenv("PPA_BENCHMARK_DISPOSABLE") != "YES":
        pytest.fail("PPA_BENCHMARK_DISPOSABLE=YES required; never run on non-disposable DB")
    if os.getenv("POSTGRES_DB") != "ppa_etl_bench02":
        pytest.fail("Refusing to truncate anything except ppa_etl_bench02")
    if os.getenv("POSTGRES_HOST") not in ("localhost", "127.0.0.1"):
        pytest.fail("Only disposable localhost PostgreSQL permitted")
    with get_db_cursor() as (_, cursor):
        cursor.execute(
            "TRUNCATE TABLE clean_users, rejected_users, stg_users_raw, "
            "final_users, etl_load_logs RESTART IDENTITY CASCADE"
        )
    monkeypatch.setattr("src.pipeline.fetch_users", lambda: [USER.copy()])


def test_control_pipeline_persists_successful_run():
    run_id = run_users_pipeline()
    assert sql_one("SELECT COUNT(*) FROM etl_load_logs WHERE run_id=%s AND status='success'", (run_id,)) == 1
    assert sql_one("SELECT COUNT(*) FROM final_users") == 2
    assert sql_one("SELECT rows_received FROM etl_load_logs WHERE run_id=%s", (run_id,)) == 8


def test_replay_does_not_change_final_business_rows():
    first = run_users_pipeline()
    before = sql_one("SELECT COUNT(*) FROM final_users")
    second = run_users_pipeline()
    after = sql_one("SELECT COUNT(*) FROM final_users")
    assert before == after == 2
    assert sql_one("SELECT rows_inserted FROM etl_load_logs WHERE run_id=%s", (first,)) == 2
    assert sql_one("SELECT rows_updated FROM etl_load_logs WHERE run_id=%s", (second,)) == 0
    assert sql_one("SELECT rows_unchanged FROM etl_load_logs WHERE run_id=%s", (second,)) == 2
    assert sql_one("SELECT COUNT(DISTINCT external_id) FROM final_users") == 2


def test_bad_inputs_are_rejected_and_audited():
    run_id = run_users_pipeline()
    assert sql_one("SELECT rows_rejected FROM etl_load_logs WHERE run_id=%s", (run_id,)) == 5
    assert sql_one("SELECT COUNT(*) FROM rejected_users WHERE run_id=%s", (run_id,)) == 5
    assert sql_one("SELECT COUNT(*) FROM rejected_users WHERE run_id=%s AND jsonb_typeof(error_details)='array'", (run_id,)) == 5
    assert sql_one("SELECT rows_clean FROM etl_load_logs WHERE run_id=%s", (run_id,)) == 3


def test_atomic_clean_rejected_load_rolls_back_on_fk_error():
    """Negative control: inject bad FK after valid clean write; expect rollback."""
    run_id = generate_run_id()
    start_run_log(run_id, "disposable_acceptance_baseline")
    load_raw_users(run_id, "disposable_acceptance_baseline", [USER])
    with get_db_cursor() as (_, cursor):
        cursor.execute("SELECT id FROM stg_users_raw WHERE run_id=%s", (run_id,))
        staging_id = cursor.fetchone()[0]
    good_clean = {
        "staging_id": staging_id,
        "external_id": 90101,
        "name": "Atomic Test User",
        "username": "atomic",
        "email": "atomic@example.com",
        "phone": None,
        "website": None,
        "company_name": None,
    }
    bad_rejected = {
        "staging_id": -1,  # Deliberately non-existent foreign key
        "raw_record": {"id": "invalid"},
        "error_details": [{"field": "external_id", "reason": "invalid"}],
    }
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        load_clean_and_rejected_records(run_id, [good_clean], [bad_rejected])
    assert sql_one("SELECT COUNT(*) FROM clean_users WHERE run_id=%s", (run_id,)) == 0
    assert sql_one("SELECT COUNT(*) FROM rejected_users WHERE run_id=%s", (run_id,)) == 0
