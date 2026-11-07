"""SQLAlchemy Core schema and intentionally isolated experiment environment.

A new PostgreSQL schema is created for each run; no user business tables are touched.
Do not run this experiment with production credentials.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

metadata = MetaData()

jobs = Table(
    "jobs", metadata,
    Column("job_id", String(80), primary_key=True),
    Column("status", String(12), nullable=False),
    CheckConstraint("status IN ('PENDING','RUNNING','RETRY','SUCCEEDED','FAILED')", name="job_state_allowed"),
    CheckConstraint("length(job_id) <= 80", name="job_id_length_allowed"),
)

# Intentionally broken legacy table: each replay creates another durable business effect.
legacy_effects = Table(
    "legacy_effects", metadata,
    Column("event_id", String(40), primary_key=True),
    Column("logical_key", String(80), nullable=False),
    Column("payload", String(500), nullable=False),
    CheckConstraint("length(event_id) <= 40", name="legacy_event_id_length_allowed"),
    CheckConstraint("length(logical_key) <= 80", name="legacy_key_length_allowed"),
    CheckConstraint("length(payload) <= 500", name="legacy_payload_length_allowed"),
)

# Corrected table: business deduplication must be a database-level invariant.
effects = Table(
    "effects", metadata,
    Column("logical_key", String(80), primary_key=True),
    Column("job_id", String(80), ForeignKey("jobs.job_id"), nullable=False, unique=True),
    Column("payload", String(500), nullable=False),
    CheckConstraint("length(logical_key) <= 80", name="effect_key_length_allowed"),
    CheckConstraint("length(job_id) <= 80", name="effect_job_id_length_allowed"),
    CheckConstraint("length(payload) <= 500", name="effect_payload_length_allowed"),
)

datasets = Table(
    "datasets", metadata,
    Column("slot", String(80), primary_key=True),
    Column("value", String(500), nullable=False),
    Column("revision", Integer, nullable=False, default=1),
    CheckConstraint("length(slot) <= 80", name="dataset_slot_length_allowed"),
    CheckConstraint("length(value) <= 500", name="dataset_value_length_allowed"),
)


def seed_job(engine: Engine, job_id: str, status: str = "PENDING") -> None:
    with engine.begin() as conn:
        conn.execute(insert(jobs).values(job_id=job_id, status=status))


def seed_dataset(engine: Engine, slot: str, value: str) -> None:
    with engine.begin() as conn:
        conn.execute(insert(datasets).values(slot=slot, value=value, revision=1))


def get_status(engine: Engine, job_id: str) -> str:
    with engine.connect() as conn:
        return conn.execute(select(jobs.c.status).where(jobs.c.job_id == job_id)).scalar_one()


def get_effect_count(engine: Engine, key: str, *, legacy: bool = False) -> int:
    from sqlalchemy import func
    table = legacy_effects if legacy else effects
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table).where(table.c.logical_key == key)).scalar_one()


def get_dataset(engine: Engine, slot: str) -> tuple[str, int]:
    with engine.connect() as conn:
        result = conn.execute(select(datasets.c.value, datasets.c.revision).where(datasets.c.slot == slot)).one()
        return result[0], result[1]


def validate_local_test_dsn(dsn: str) -> None:
    """Fail closed before connecting. v0.2 intentionally supports ONE disposable local test DB.

    Not an authorization boundary against a malicious local administrator; rejects
    accidental remote/production DSNs, unsafe URL parameters and arbitrary DBs.
    """
    if not dsn or any(ord(c) < 32 for c in dsn):
        raise ValueError("Expected a non-empty local PostgreSQL test DSN")
    try:
        url = make_url(dsn)
    except Exception:
        raise ValueError("Invalid local PostgreSQL test DSN") from None
    if (
        url.drivername != "postgresql+psycopg"
        or url.username != "acceptance"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.port != 54329
        or url.database != "acceptance"
        or not url.password
        or url.query
    ):
        raise ValueError(
            "Refusing DSN: only postgresql+psycopg://acceptance:<secret>@"
            "localhost:54329/acceptance (or loopback IP) is permitted"
        )


def enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Keep SQLite's FK behavior aligned with the PostgreSQL experiment."""
    if engine.dialect.name != "sqlite":
        raise ValueError("SQLite engine required")

    @event.listens_for(engine, "connect")
    def _foreign_keys_on(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


@contextmanager
def isolated_engine(dsn: str | None = None, sqlite_path: Path | None = None) -> Iterator[Engine]:
    """Create and remove *only* a random namespace on a disposable loopback database.

    PostgreSQL is deliberately restricted to the compose service at localhost:54329.
    SQLite operates on local memory or a supplied temporary path.
    """
    if dsn is not None:
        validate_local_test_dsn(dsn)
        raw_engine = create_engine(
            dsn,
            future=True,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 5, "options": "-c statement_timeout=10000 -c lock_timeout=3000"},
        )
        schema = "acceptance_" + uuid4().hex[:24]
        created = False
        try:
            # Generated schema is random lowercase hex; no caller SQL identifier is interpolated.
            with raw_engine.begin() as conn:
                conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
                created = True
            engine = raw_engine.execution_options(schema_translate_map={None: schema})
            metadata.create_all(engine)
            yield engine
        finally:
            try:
                if created:
                    with raw_engine.begin() as conn:
                        conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            finally:
                raw_engine.dispose()
    else:
        url = "sqlite+pysqlite:///:memory:" if sqlite_path is None else f"sqlite+pysqlite:///{sqlite_path.as_posix()}"
        engine = create_engine(url, future=True, hide_parameters=True)
        enable_sqlite_foreign_keys(engine)
        try:
            metadata.create_all(engine)
            yield engine
        finally:
            engine.dispose()
