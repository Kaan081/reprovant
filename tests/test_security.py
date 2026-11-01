"""Fail-closed security preflight for the disposable experiment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import inspect

from pipeline_acceptance.demo import run_cases
from pipeline_acceptance.storage import isolated_engine, validate_local_test_dsn, seed_job, get_status


@pytest.mark.parametrize("dsn", [
    "postgresql+psycopg://acceptance:token@prod.example.com:54329/acceptance",
    "postgresql+psycopg://acceptance:token@localhost:5432/acceptance",
    "postgresql+psycopg://admin:token@localhost:54329/acceptance",
    "postgresql+psycopg://acceptance:token@localhost:54329/production",
    "postgresql+psycopg://acceptance:token@localhost:54329/postgres",
    "postgresql+psycopg://acceptance:token@localhost:54329/acceptance?options=-csearch_path%3Dpublic",
    "postgresql+psycopg://acceptance@localhost:54329/acceptance",
    "postgresql+psycopg://acceptance:token@localhost:54329/acceptance\nEXTRA",
    "sqlite+pysqlite:///:memory:",
    "not a url", "",
])
def test_unsafe_dsn_rejected_before_connection(dsn):
    with pytest.raises(ValueError):
        validate_local_test_dsn(dsn)


def test_only_disposable_test_endpoint_passes_preflight():
    validate_local_test_dsn("postgresql+psycopg://acceptance:random_local_secret@localhost:54329/acceptance")
    validate_local_test_dsn("postgresql+psycopg://acceptance:random_local_secret@127.0.0.1:54329/acceptance")


def test_report_never_contains_dsn(monkeypatch):
    secret = "very_private_no_logging_123"
    monkeypatch.setenv("PIPELINE_TEST_DSN", f"postgresql+psycopg://acceptance:{secret}@localhost:54329/acceptance")
    report = run_cases()  # Default path must never connect just because env var exists.
    dump = json.dumps(report)
    assert secret not in dump
    assert "postgresql+psycopg" not in dump
    assert report["backend"] == "sqlite"


def test_sql_parameter_binding_with_hostile_job_identifier(engine):
    job = "x'); DROP TABLE jobs; --"
    seed_job(engine, job)
    assert get_status(engine, job) == "PENDING"
    # Inspector ignores schema_translate_map; explicitly inspect the isolated PG schema.
    schema = engine.get_execution_options().get("schema_translate_map", {}).get(None)
    assert "jobs" in inspect(engine).get_table_names(schema=schema)


def test_cli_never_accepts_dsn_in_argument():
    p = subprocess.run([sys.executable, "-m", "pipeline_acceptance.demo", "--dsn", "secret"],
                       text=True, capture_output=True)
    assert p.returncode != 0
    assert "unrecognized arguments" in p.stderr


def test_cli_opt_in_required_for_postgresql(monkeypatch):
    env = dict(os.environ)
    env.pop("PIPELINE_TEST_DSN", None)
    p = subprocess.run([sys.executable, "-m", "pipeline_acceptance.demo", "--postgres"],
                       text=True, capture_output=True, env=env)
    assert p.returncode != 0
    assert "requires PIPELINE_TEST_DSN" in p.stderr


def test_secret_glob_patterns_documented_in_gitignore():
    ignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
    for pattern in [".env", ".env.*", "*.env", "*.env.*", "*.pem", "*.key", "*.dump", "*.log"]:
        assert pattern in ignore.splitlines()


def test_compose_requires_password_without_embedded_default():
    body = (Path(__file__).resolve().parents[1] / "compose.yaml").read_text(encoding="utf-8")
    assert "${PIPELINE_DB_PASSWORD:?" in body
    assert '127.0.0.1:54329:5432' in body
    assert "acceptance_local_only" not in body
