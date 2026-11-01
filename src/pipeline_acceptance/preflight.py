"""Fast, secret-safe local PostgreSQL readiness checks (not a production validator)."""
from __future__ import annotations

import socket

from sqlalchemy.engine.url import make_url

from .storage import validate_local_test_dsn


class TestDatabaseUnavailable(RuntimeError):
    """Raised before running tests against an unavailable disposable database."""


def require_postgres_ready(dsn: str) -> None:
    """Check opt-in disposable Postgres once, rather than time out for each test.

    This check is a developer-experience preflight, not a security guarantee and
    not proof the database will remain available throughout the test run.
    """
    validate_local_test_dsn(dsn)
    try:
        with socket.create_connection(("127.0.0.1", 54329), timeout=1.0):
            pass
    except OSError:
        raise TestDatabaseUnavailable(
            "Local PostgreSQL test service is unavailable on 127.0.0.1:54329. "
            "Start Docker Desktop, run 'docker compose up -d --wait postgres', "
            "or unset PIPELINE_TEST_DSN to run only SQLite tests."
        ) from None

    try:
        import psycopg
    except ImportError:
        raise TestDatabaseUnavailable(
            "Missing psycopg driver. Run: python -m pip install -e '.[test,postgres]'"
        ) from None
    try:
        # `postgresql+psycopg://` is SQLAlchemy-specific; libpq/psycopg cannot
        # parse that URL scheme directly. Use the already-validated components.
        url = make_url(dsn)
        with psycopg.connect(
            host=url.host,
            port=url.port,
            dbname=url.database,
            user=url.username,
            password=url.password,
            connect_timeout=3,
            options="-c statement_timeout=3000",
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
    except (psycopg.Error, OSError):
        raise TestDatabaseUnavailable(
            "Disposable PostgreSQL is reachable but authentication or SQL readiness failed. "
            "Verify the Compose service and that PIPELINE_DB_PASSWORD matches the "
            "password used when the container first started. No connection string is logged."
        ) from None
