from __future__ import annotations

import os
import pytest

from pipeline_acceptance.preflight import TestDatabaseUnavailable, require_postgres_ready
from pipeline_acceptance.storage import isolated_engine


def pytest_sessionstart(session):
    # The opt-in DSN is authoritative: reject misconfiguration once, early,
    # instead of timing out separately for every PostgreSQL-backed test.
    dsn = os.environ.get("PIPELINE_TEST_DSN")
    if dsn is not None:
        try:
            require_postgres_ready(dsn)
        except (TestDatabaseUnavailable, ValueError) as exc:
            pytest.exit(f"PostgreSQL preflight failed: {exc}", returncode=4)


@pytest.fixture
def engine(tmp_path):
    with isolated_engine(os.environ.get("PIPELINE_TEST_DSN"), sqlite_path=tmp_path / "acceptance.db") as e:
        yield e
