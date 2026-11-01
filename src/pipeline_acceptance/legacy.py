"""Intentionally broken patterns, used only to demonstrate failures."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import insert, update
from sqlalchemy.engine import Engine

from .storage import datasets, jobs, legacy_effects


class AckLostAfterCommit(RuntimeError):
    """Simulates process death after durable commit but before the queue ACK."""


def process_with_bug(engine: Engine, job_id: str, logical_key: str, payload: str, *, crash_after_commit: bool = False) -> None:
    # Bad: no business idempotency constraint; replay inserts another event.
    with engine.begin() as conn:
        conn.execute(insert(legacy_effects).values(event_id=uuid4().hex, logical_key=logical_key, payload=payload))
        conn.execute(update(jobs).where(jobs.c.job_id == job_id).values(status="SUCCEEDED"))
    if crash_after_commit:
        raise AckLostAfterCommit("Simulated crash after COMMIT, before ACK")


def stale_running_update_with_bug(engine: Engine, job_id: str) -> None:
    # Bad: stale worker overwrites terminal success unconditionally.
    with engine.begin() as conn:
        conn.execute(update(jobs).where(jobs.c.job_id == job_id).values(status="RUNNING"))


def update_dataset_with_bug(engine: Engine, job_id: str, slot: str, candidate: str, *, valid: bool) -> None:
    # Bad: data write happens before validation and leaves a committed corruption.
    with engine.begin() as conn:
        conn.execute(update(datasets).where(datasets.c.slot == slot).values(value=candidate, revision=datasets.c.revision + 1))
        conn.execute(update(jobs).where(jobs.c.job_id == job_id).values(status="SUCCEEDED"))
    if not valid:
        raise ValueError("Validation failed, but previous commit already happened")
