"""04B: use the v0 replay contract with a pinned *real* Eventflow worker.

A disposable GitHub-hosted PostgreSQL + Redis + Celery stack is required.
Re-uses verified 03A probe helpers without modifying the original 03A/03B runs.
The second dispatch is MANUAL, not broker redelivery/ACK-loss recovery.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

from pipeline_acceptance.replay_contract import (
    SCHEMA, ReplayContract, Snapshot, evaluate_replay, write_evidence,
)

PIN = "c08455d626d5e1c316d932c4da0652086fb1b19e"
HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
PROBE_PATH = ROOT / "experiments/eventflow_worker_probe/run_probe.py"


def load_probe():
    spec = importlib.util.spec_from_file_location("eventflow_03a_probe_04b", PROBE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Missing pinned 03A probe helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_changed_files(mode: str) -> list[str]:
    if mode == "upstream":
        return []
    if mode == "guarded":
        return ["orders/tasks.py"]
    raise ValueError("Unsupported mode")


def classify_run(mode: str, sha: str, changed: list[str], evidence: dict, checks: dict) -> dict:
    """Fail-closed outer classifier: v0 contract alone does NOT attest a real worker."""
    result = {
        "experiment": "eventflow-replay-contract-04b",
        "mode": mode,
        "status": "INCONCLUSIVE",
        "reason": "incomplete_evidence",
        "source_pin": sha,
        "changed_upstream_files": changed,
        "contract_report": evidence,
        "worker_attestation": checks,
        "scope": "one manual repeated dispatch, pinned educational Eventflow; disposable real Celery+Redis+PostgreSQL; NOT broker ACK-loss or production certification",
    }
    if sha != PIN or changed != expected_changed_files(mode):
        result["reason"] = "source_provenance_mismatch"
        return result
    mandatory = (
        checks.get("worker_seen") is True,
        checks.get("eager_mode") is False,
        checks.get("first_task_state") == "SUCCESS",
        checks.get("first_status") == "confirmed",
        checks.get("first_confirmed_events") == 1,
        checks.get("shipped_transition_rows") == 1,
        checks.get("second_task_state") == "SUCCESS",
        checks.get("distinct_task_ids") is True,
        checks.get("task_acks_late") is False,
        checks.get("task_reject_on_worker_lost") is False,
        bool(checks.get("worker_names")),
        checks.get("subscription_confirmed") is True,
        evidence.get("schema_version") == SCHEMA,
        evidence.get("dispatch_completed") is True,
        evidence.get("before") == {"state": "shipped", "effects": {"order_confirmed": 1}},
        evidence.get("checks") == {
            "state_preserved": mode == "guarded",
            "effect:order_confirmed": mode == "guarded",
        },
    )
    if not all(mandatory):
        result["reason"] = "missing_worker_or_contract_evidence"
        return result
    if mode == "upstream":
        if (evidence.get("status") == "RED" and
            evidence.get("after") == {"state": "confirmed", "effects": {"order_confirmed": 2}} and
            set(evidence.get("failed_checks", [])) == {"state_preserved", "effect:order_confirmed"}):
            result.update(status="VERIFIED_RED_CONTROL", reason="manual_duplicate_dispatch_reproduced")
        else:
            result.update(status="FAIL", reason="expected_red_not_observed")
    else:
        if (evidence.get("status") == "GREEN" and
            evidence.get("after") == {"state": "shipped", "effects": {"order_confirmed": 1}}):
            result.update(status="VERIFIED_GUARDED_GREEN", reason="manual_replay_invariants_preserved")
        else:
            result.update(status="FAIL", reason="expected_guarded_green_not_observed")
    return result


class EventflowAdapter:
    """Application-specific thin adapter. The v0 core never imports Django/Celery."""

    def __init__(self, order: Any, task: Any, pubsub: Any, probe: Any, attestation: dict, first_id: str):
        self.order = order
        self.task = task
        self.pubsub = pubsub
        self.probe = probe
        self.attestation = attestation
        self.first_id = first_id
        self.confirmations = 1  # independently observed before the SHIPPED transition

    def is_disposable(self) -> bool:
        self.probe.assert_disposable()
        return self.probe.read_upstream_revision() == PIN

    def observe(self) -> Snapshot:
        self.order.refresh_from_db()
        return Snapshot(state=self.order.status, effects={"order_confirmed": self.confirmations})

    def dispatch(self) -> None:
        second = self.task.apply_async(args=[self.order.pk])
        self.attestation["distinct_task_ids"] = bool(second.id and self.first_id and second.id != self.first_id)
        if not self.attestation["distinct_task_ids"]:
            raise RuntimeError("Second dispatch did not have a distinct task id")
        second.get(timeout=40, propagate=True)
        self.attestation["second_task_state"] = second.state
        if second.state != "SUCCESS":
            raise RuntimeError("Second task did not complete successfully")
        events = self.probe.gather_events(self.pubsub, self.order.pk, seconds=2.0)
        if any(event.get("type") != "order.confirmed" for event in events):
            raise RuntimeError("Unexpected captured event")
        self.confirmations += len(events)


def run_live(mode: str, changed: list[str]) -> dict:
    probe = load_probe()
    probe.assert_disposable()
    sha = probe.read_upstream_revision()
    if sha != PIN or changed != expected_changed_files(mode):
        return classify_run(mode, sha, changed, {}, {})

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from config.celery import app
    from orders.events import get_redis_client
    from orders.models import Order
    from orders.tasks import process_new_order

    if bool(app.conf.task_always_eager) or bool(settings.CELERY_TASK_ALWAYS_EAGER):
        raise RuntimeError("Eager simulation forbidden")
    worker_names = probe.await_worker(app)
    info = {
        "worker_seen": bool(worker_names),
        "worker_names": worker_names,
        "eager_mode": False,
        "task_acks_late": bool(process_new_order.acks_late),
        "task_reject_on_worker_lost": bool(process_new_order.reject_on_worker_lost),
        "subscription_confirmed": False,
        "first_task_state": "NOT_RUN",
        "second_task_state": "NOT_RUN",
        "distinct_task_ids": False,
    }

    redis = get_redis_client()
    redis.ping()
    pubsub = redis.pubsub()
    try:
        pubsub.subscribe(settings.ORDER_EVENTS_CHANNEL)
        reply = pubsub.get_message(timeout=5)
        if not reply or reply.get("type") != "subscribe":
            raise RuntimeError("Redis pubsub subscription not confirmed")
        info["subscription_confirmed"] = True

        order = Order.objects.create(customer_email="probe04b@example.invalid", amount_cents=5000)
        first = process_new_order.apply_async(args=[order.pk])
        first.get(timeout=40, propagate=True)
        info["first_task_state"] = first.state
        order.refresh_from_db()
        info["first_status"] = order.status
        events = probe.gather_events(pubsub, order.pk, seconds=2.0)
        info["first_confirmed_events"] = len(events)
        if first.state != "SUCCESS" or order.status != Order.Status.CONFIRMED or len(events) != 1:
            raise RuntimeError("First dispatch positive control failed")

        changed_rows = Order.objects.filter(pk=order.pk, status=Order.Status.CONFIRMED).update(status=Order.Status.SHIPPED)
        info["shipped_transition_rows"] = changed_rows
        if changed_rows != 1:
            raise RuntimeError("Could not establish SHIPPED baseline")

        adapter = EventflowAdapter(order, process_new_order, pubsub, probe, info, first.id)
        contract = ReplayContract("eventflow-no-regression", "shipped", {"order_confirmed": 1})
        replay = evaluate_replay(adapter, contract)
        return classify_run(mode, sha, changed, replay, info)
    finally:
        pubsub.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["upstream", "guarded"], required=True)
    parser.add_argument("--changed-files", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        changed = [x.strip() for x in args.changed_files.read_text(encoding="utf8").splitlines() if x.strip()]
        report = run_live(args.mode, changed)
    except Exception as exc:
        # Do not serialize exception content or traceback; they may contain secrets.
        report = {"experiment": "eventflow-replay-contract-04b", "mode": args.mode,
                  "status": "INCONCLUSIVE", "reason": "experiment_exception", "error_type": type(exc).__name__}
    write_evidence(args.output, report)
    print("REPROVANT EVENTFLOW 04B:", args.mode, report["status"], report["reason"])
    expected = "VERIFIED_RED_CONTROL" if args.mode == "upstream" else "VERIFIED_GUARDED_GREEN"
    return 0 if report["status"] == expected else 2


if __name__ == "__main__":
    raise SystemExit(main())
