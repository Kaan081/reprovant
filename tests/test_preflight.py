"""No database needed: verify failure modes safely and quickly."""
from __future__ import annotations

import pytest

from pipeline_acceptance import preflight

DSN = "postgresql+psycopg://acceptance:dummy_secret@localhost:54329/acceptance"


def test_preflight_refuses_remote_before_touching_network(monkeypatch):
    def forbidden_connection(*_args, **_kwargs):
        raise AssertionError("preflight must validate the endpoint before touching the network")
    monkeypatch.setattr(preflight.socket, "create_connection", forbidden_connection)
    with pytest.raises(ValueError, match="Refusing DSN"):
        preflight.require_postgres_ready(
            "postgresql+psycopg://acceptance:secret@remote.example.com:54329/acceptance"
        )


def test_preflight_unreachable_postgres_gives_actionable_error_without_secret(monkeypatch):
    def connection_refused(*_args, **_kwargs):
        raise ConnectionRefusedError("simulated network unavailable")
    monkeypatch.setattr(preflight.socket, "create_connection", connection_refused)
    with pytest.raises(preflight.TestDatabaseUnavailable) as err:
        preflight.require_postgres_ready(DSN)
    assert "Docker Desktop" in str(err.value)
    assert "dummy_secret" not in str(err.value)


def test_optional_postgres_only_when_env_present():
    # The main test suite handles PostgreSQL opt-in explicitly. This confirms
    # that a missing DSN cannot implicitly select a production database.
    from pipeline_acceptance.demo import run_cases
    assert run_cases()["backend"] == "sqlite"
