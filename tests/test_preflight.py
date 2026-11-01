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


def test_preflight_passes_parsed_components_to_psycopg_not_sqlalchemy_url(monkeypatch):
    """Psycopg uses libpq conninfo, not SQLAlchemy's postgresql+psycopg URL scheme."""
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace

    seen = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            assert statement == "SELECT 1"

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return FakeCursor()

    def fake_connect(*args, **kwargs):
        assert not args, "SQLAlchemy URL must not be passed as libpq conninfo"
        seen.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(preflight.socket, "create_connection", lambda *_a, **_k: nullcontext())
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=fake_connect, Error=Exception))

    preflight.require_postgres_ready(
        "postgresql+psycopg://acceptance:p%40ss%3Aword@localhost:54329/acceptance"
    )
    assert seen["host"] == "localhost"
    assert seen["port"] == 54329
    assert seen["user"] == "acceptance"
    assert seen["dbname"] == "acceptance"
    assert seen["password"] == "p@ss:word"
    assert seen["connect_timeout"] == 3
    assert seen["options"] == "-c statement_timeout=3000"
