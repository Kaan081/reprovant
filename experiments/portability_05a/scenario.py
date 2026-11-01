"""05A: independent Flask/Celery job lifecycle, one manual second dispatch.

No source changes to the pinned public example. Does not assert repeated external effects.
Run only against the disposable CI services, not an application database.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

PIN = "509eda4df11d0a79b314494104a7e60aa176f693"
ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "external-queue-app"
DB_URL = "postgresql+psycopg2://postgres:05a-disposable-only@127.0.0.1:5432/ppa_portability_05a"
REDIS_URL = "redis://127.0.0.1:6379/14"


def assert_disposable():
    if (os.getenv("PPA_PORTABILITY_DISPOSABLE") != "YES"
            or os.getenv("DATABASE_URL") != DB_URL
            or os.getenv("REDIS_URL") != REDIS_URL):
        raise RuntimeError("Refusing non-disposable or unexpected service configuration")
    sha = subprocess.check_output(
        ["git", "-C", str(APP), "rev-parse", "HEAD"], text=True,
    ).strip()
    if sha != PIN:
        raise RuntimeError("Unexpected external application revision")


class JobScenario:
    def __init__(self):
        self.app = None
        self.job_id = None
        self.first_id = None
        self.task = None
        self.celery = None
        self.attestation = {"worker_seen": False, "eager_mode": None,
                            "first_task_state": "NOT_RUN", "second_task_state": "NOT_RUN",
                            "distinct_task_ids": False}

    def is_disposable(self):
        assert_disposable()
        return True

    def prepare(self):
        self.is_disposable()
        from python_queues.app import create_app
        from python_queues.app.extensions import db
        from python_queues.app.models.job import Job
        from python_queues.app.workers.celery_app import celery
        from python_queues.app.workers.tasks import process_job

        self.app = create_app()
        self.celery, self.task = celery, process_job
        eager = bool(celery.conf.task_always_eager)
        self.attestation["eager_mode"] = eager
        if eager:
            raise RuntimeError("Celery eager mode prohibited")

        workers = []
        for _ in range(25):
            replies = celery.control.ping(timeout=1) or []
            workers = [name for reply in replies for name in reply]
            if workers:
                break
            time.sleep(0.5)
        if not workers:
            raise RuntimeError("No separate Celery worker responded")
        self.attestation["worker_seen"] = True

        with self.app.app_context():
            job = Job(type="05a-test", payload={"synthetic": True})
            db.session.add(job)
            db.session.commit()
            self.job_id = job.id

        first = self.task.apply_async(args=[self.job_id])
        first.get(timeout=40, propagate=True)
        self.attestation["first_task_state"] = first.state
        self.first_id = first.id
        if first.state != "SUCCESS" or self.observe() != {"state": "success", "attempts": 1}:
            raise RuntimeError("First dispatch positive control failed")

    def observe(self):
        from python_queues.app.extensions import db
        from python_queues.app.models.job import Job
        if self.app is None or self.job_id is None:
            raise RuntimeError("Scenario not prepared")
        with self.app.app_context():
            db.session.expire_all()
            job = db.session.get(Job, self.job_id)
            if job is None:
                raise RuntimeError("Job disappeared")
            return {"state": job.status.value, "attempts": job.attempts}

    def dispatch(self):
        second = self.task.apply_async(args=[self.job_id])
        self.attestation["distinct_task_ids"] = bool(
            second.id and self.first_id and second.id != self.first_id
        )
        if not self.attestation["distinct_task_ids"]:
            raise RuntimeError("No distinct second task ID")
        second.get(timeout=40, propagate=True)
        self.attestation["second_task_state"] = second.state
        if second.state != "SUCCESS":
            raise RuntimeError("Second task did not succeed")
