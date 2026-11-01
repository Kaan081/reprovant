"""04C: an ordinary pytest acceptance test, no ReplayContract dependency.

Requires the same disposable, pinned Eventflow + Celery/Redis/PostgreSQL stack as 04B.
This is one MANUAL second enqueue, not natural broker redelivery or ACK loss.
Both acceptance tests share one session-scoped exercise to avoid double-dispatch.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

PIN = "c08455d626d5e1c316d932c4da0652086fb1b19e"
ROOT = Path(__file__).resolve().parents[2]
HELPERS = ROOT / "experiments/eventflow_worker_probe/run_probe.py"


def _load_helpers():
    spec = importlib.util.spec_from_file_location("eventflow_03a_helpers_04c", HELPERS)
    if spec is None or spec.loader is None:
        raise RuntimeError("03A environment helpers missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def observed():
    """One real enqueue + manual repeat; no Reprovant report/evaluator calls."""
    probe = _load_helpers()
    probe.assert_disposable()
    upstream_sha = probe.read_upstream_revision()
    if upstream_sha != PIN:
        raise RuntimeError("Unpinned upstream source")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()
    from django.conf import settings
    from config.celery import app
    from orders.events import get_redis_client
    from orders.models import Order
    from orders.tasks import process_new_order

    if bool(app.conf.task_always_eager) or bool(settings.CELERY_TASK_ALWAYS_EAGER):
        raise RuntimeError("Refusing Celery eager simulation")
    worker_names = probe.await_worker(app)
    if not worker_names:
        raise RuntimeError("No live worker attested")
    if bool(process_new_order.acks_late) or bool(process_new_order.reject_on_worker_lost):
        raise RuntimeError("Task flags differ from 04B acceptance scope")

    redis = get_redis_client()
    redis.ping()
    pubsub = redis.pubsub()
    try:
        pubsub.subscribe(settings.ORDER_EVENTS_CHANNEL)
        reply = pubsub.get_message(timeout=5)
        if not reply or reply.get("type") != "subscribe":
            raise RuntimeError("Redis pubsub subscription not confirmed")

        order = Order.objects.create(customer_email="pytest04c@example.invalid", amount_cents=5000)
        first = process_new_order.apply_async(args=[order.pk])
        first.get(timeout=40, propagate=True)
        order.refresh_from_db()
        first_events = probe.gather_events(pubsub, order.pk, seconds=2.0)
        if first.state != "SUCCESS" or order.status != Order.Status.CONFIRMED or len(first_events) != 1:
            raise RuntimeError("Positive control was not established")
        if Order.objects.filter(pk=order.pk, status=Order.Status.CONFIRMED).update(
                status=Order.Status.SHIPPED) != 1:
            raise RuntimeError("Cannot establish SHIPPED baseline")
        order.refresh_from_db()
        if order.status != Order.Status.SHIPPED:
            raise RuntimeError("Baseline state unexpectedly changed")

        second = process_new_order.apply_async(args=[order.pk])
        if not second.id or not first.id or second.id == first.id:
            raise RuntimeError("Distinct task ID not observed")
        second.get(timeout=40, propagate=True)
        if second.state != "SUCCESS":
            raise RuntimeError("Second task did not complete successfully")
        order.refresh_from_db()
        second_events = probe.gather_events(pubsub, order.pk, seconds=2.0)
        result = {
            "source_pin": upstream_sha,
            "worker_seen": True,
            "eager_mode": False,
            "subscription_confirmed": True,
            "task_acks_late": False,
            "task_reject_on_worker_lost": False,
            "first_task_state": first.state,
            "second_task_state": second.state,
            "distinct_task_ids": second.id != first.id,
            "before": {"state": "shipped", "order_confirmed": len(first_events)},
            "after": {"state": order.status, "order_confirmed": len(first_events) + len(second_events)},
        }
        # Written only after the entire setup and both dispatches completed.
        destination = os.environ.get("EVENTFLOW_04C_SNAPSHOT")
        if not destination:
            raise RuntimeError("EVENTFLOW_04C_SNAPSHOT output path required")
        Path(destination).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result
    finally:
        pubsub.close()


def test_terminal_state_preserved(observed):
    if observed["after"]["state"] != "shipped":
        pytest.fail("INVARIANT_STATE_REGRESSION", pytrace=False)


def test_no_duplicate_confirmation(observed):
    if observed["after"]["order_confirmed"] != 1:
        pytest.fail("INVARIANT_DUPLICATE_CONFIRMATION", pytrace=False)
