"""Corrected implementation built with standard database/SQLAlchemy primitives.

This demonstrates a baseline correction, not a new library's superiority.
"""
from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.engine import Engine

from .legacy import AckLostAfterCommit
from .storage import datasets, effects, jobs


def _insert_effect_on_conflict_do_nothing(engine: Engine, *, job_id: str, logical_key: str, payload: str):
    # Both dialects compile ON CONFLICT against the logical key OR job_id uniqueness constraints.
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif engine.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise ValueError("Only PostgreSQL and local SQLite demo backends supported")
    return insert(effects).values(logical_key=logical_key, job_id=job_id, payload=payload).on_conflict_do_nothing()


def process_once(engine: Engine, job_id: str, logical_key: str, payload: str, *, crash_after_commit: bool = False) -> None:
    """Idempotent replay of same job/logical effect; commit happens before simulated ACK.

    If logical_key was previously written with conflicting content, fail closed.
    Job state must already exist. Status update only moves nonterminal states to success.
    """
    from sqlalchemy import select

    if not logical_key.strip():
        raise ValueError("Logical idempotency key cannot be empty")
    with engine.begin() as conn:
        conn.execute(_insert_effect_on_conflict_do_nothing(engine, job_id=job_id, logical_key=logical_key, payload=payload))
        stored = conn.execute(
            select(effects.c.job_id, effects.c.payload).where(effects.c.logical_key == logical_key)
        ).one_or_none()
        if stored is None or (stored.job_id, stored.payload) != (job_id, payload):
            raise ValueError("Idempotency-key collision with different job, key or payload")
        conn.execute(
            update(jobs)
            .where(jobs.c.job_id == job_id, jobs.c.status.in_(["PENDING", "RUNNING", "RETRY"]))
            .values(status="SUCCEEDED")
        )
        # A missing or FAILED job cannot be silently accepted. Replays of SUCCEEDED are allowed.
        state = conn.execute(select(jobs.c.status).where(jobs.c.job_id == job_id)).scalar_one_or_none()
        if state != "SUCCEEDED":
            raise ValueError("Cannot mark missing/failed job as succeeded")
    if crash_after_commit:
        raise AckLostAfterCommit("Simulated crash after COMMIT, before ACK")


def try_mark_running(engine: Engine, job_id: str) -> bool:
    """Stale worker may only transition PENDING/RETRY -> RUNNING."""
    with engine.begin() as conn:
        result = conn.execute(
            update(jobs)
            .where(jobs.c.job_id == job_id, jobs.c.status.in_(["PENDING", "RETRY"]))
            .values(status="RUNNING")
        )
        return result.rowcount == 1


def accept_validated_dataset(engine: Engine, job_id: str, slot: str, candidate: str, *, valid: bool) -> None:
    """Validate before any durable write; reject an invalid candidate atomically."""
    if not valid:
        raise ValueError("Validation failed; database was not modified")
    if not candidate.strip():
        raise ValueError("Empty dataset payload")
    with engine.begin() as conn:
        # Guard on the same transactional UPDATE that transitions the state. This
        # locks/rechecks the current state in PostgreSQL under competing writers.
        transitioned = conn.execute(
            update(jobs)
            .where(jobs.c.job_id == job_id, jobs.c.status.in_(["PENDING", "RUNNING", "RETRY"]))
            .values(status="SUCCEEDED")
        )
        if transitioned.rowcount != 1:
            raise ValueError("Job is terminal or missing")
        result = conn.execute(
            update(datasets)
            .where(datasets.c.slot == slot)
            .values(value=candidate, revision=datasets.c.revision + 1)
        )
        if result.rowcount != 1:
            raise ValueError("Unknown dataset slot")
