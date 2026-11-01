"""Live Celery broker duplicate-dispatch probe of a pinned external demo.

This deliberately does NOT claim worker death, broker redelivery, or ACK-loss.
Outcome OBSERVED_RED is expected for the frozen unmodified upstream.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
import sys
import time
import traceback
from datetime import datetime, timezone

UPSTREAM_SHA = "c08455d626d5e1c316d932c4da0652086fb1b19e"
UPSTREAM_REPO = "juneja-varun/eventflow"


def read_upstream_revision() -> str:
    """Read the pinned external checkout, never our experiment repo HEAD."""
    upstream_dir = Path(__file__).resolve().parents[2] / "upstream-eventflow"
    return subprocess.check_output(
        ["git", "-C", str(upstream_dir), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def classify(observation: dict) -> tuple[str, str]:
    """Pure fail-closed oracle, independently testable without Django/Celery."""
    if not observation.get("worker_seen") or observation.get("eager_mode") is not False:
        return "INCONCLUSIVE", "real_worker_not_verified"
    if observation.get("first_task_state") != "SUCCESS":
        return "INCONCLUSIVE", "first_task_did_not_succeed"
    if observation.get("first_status") != "confirmed" or observation.get("first_confirmed_events") != 1:
        return "INCONCLUSIVE", "positive_control_failed"
    if observation.get("second_task_state") != "SUCCESS":
        return "INCONCLUSIVE", "second_task_did_not_succeed"
    if observation.get("status_after_manual_reenqueue") == "confirmed" and observation.get("confirmed_events_total") == 2:
        return "OBSERVED_RED", "shipped_regressed_and_duplicate_confirmed_event"
    if observation.get("status_after_manual_reenqueue") == "shipped" and observation.get("confirmed_events_total") == 1:
        return "NOT_REPRODUCED", "upstream_behaved_as_guarded"
    return "INCONCLUSIVE", "partial_or_ambiguous_observation"


def assert_disposable() -> None:
    if os.environ.get("EVENTFLOW_PROBE_DISPOSABLE") != "YES":
        raise RuntimeError("Refusing run: EVENTFLOW_PROBE_DISPOSABLE=YES required")
    if os.environ.get("POSTGRES_DB") != "ppa_eventflow_worker_ci":
        raise RuntimeError("Refusing run: disposable Postgres DB name mismatch")
    if os.environ.get("POSTGRES_HOST") not in ("127.0.0.1", "localhost"):
        raise RuntimeError("Refusing run: only localhost disposable Postgres permitted")
    if os.environ.get("REDIS_URL") != "redis://127.0.0.1:6379/14":
        raise RuntimeError("Refusing run: dedicated disposable Redis DB 14 required")


def await_worker(app, seconds: float = 35.0) -> list[str]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            replies = app.control.ping(timeout=1) or []
            names = [name for item in replies for name in item]
            if names:
                return names
        except Exception:
            pass
        time.sleep(0.8)
    raise RuntimeError("No independent Celery worker replied to broker ping")


def gather_events(pubsub, order_id: int, seconds: float) -> list[dict]:
    deadline = time.monotonic() + seconds
    events: list[dict] = []
    while time.monotonic() < deadline:
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if not message or message.get("type") != "message":
            continue
        try:
            event = json.loads(message["data"])
        except (TypeError, ValueError):
            continue
        if event.get("payload", {}).get("order_id") == order_id and event.get("type") == "order.confirmed":
            events.append({"type": "order.confirmed", "order_id": order_id})
    return events


def exercise(observation: dict) -> None:
    assert_disposable()
    upstream_revision = read_upstream_revision()
    observation["upstream_revision"] = upstream_revision
    if upstream_revision != UPSTREAM_SHA:
        raise RuntimeError("Refusing non-pinned upstream revision")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from config.celery import app
    from orders.events import get_redis_client
    from orders.models import Order
    from orders.tasks import process_new_order

    eager = bool(app.conf.task_always_eager)
    observation["eager_mode"] = eager
    if eager or settings.CELERY_TASK_ALWAYS_EAGER:
        raise RuntimeError("Refusing eager Celery simulation; must use a separate worker")

    names = await_worker(app)
    observation["worker_seen"] = True
    observation["worker_names"] = names
    observation["task_name"] = process_new_order.name
    observation["task_acks_late"] = bool(process_new_order.acks_late)
    observation["task_reject_on_worker_lost"] = bool(process_new_order.reject_on_worker_lost)

    client = get_redis_client()
    client.ping()
    pubsub = client.pubsub()
    try:
        pubsub.subscribe(settings.ORDER_EVENTS_CHANNEL)
        # Require a confirmed subscription before creating/publishing anything.
        reply = pubsub.get_message(timeout=5)
        if not reply or reply.get("type") != "subscribe":
            raise RuntimeError("Redis pubsub subscription not confirmed")

        order = Order.objects.create(customer_email="probe@example.invalid", amount_cents=5000)
        order_id = order.pk
        observation["order_id"] = order_id
        task1 = process_new_order.apply_async(args=[order_id])
        observation["first_task_id"] = task1.id
        task1.get(timeout=40, propagate=True)
        observation["first_task_state"] = task1.state
        order.refresh_from_db()
        observation["first_status"] = order.status
        all_events = gather_events(pubsub, order_id, seconds=2.0)
        observation["first_confirmed_events"] = len(all_events)
        if order.status != Order.Status.CONFIRMED or len(all_events) != 1:
            return

        # Model the order's subsequent legitimate advancement as an external service.
        Order.objects.filter(pk=order_id).update(status=Order.Status.SHIPPED)
        order.refresh_from_db()
        if order.status != Order.Status.SHIPPED:
            raise RuntimeError("Failed to establish SHIPPED before duplicate dispatch")

        # Intentional second Celery delivery with a new task ID. NOT a broker replay.
        task2 = process_new_order.apply_async(args=[order_id])
        observation["second_task_id"] = task2.id
        task2.get(timeout=40, propagate=True)
        observation["second_task_state"] = task2.state
        order.refresh_from_db()
        observation["status_after_manual_reenqueue"] = order.status
        all_events.extend(gather_events(pubsub, order_id, seconds=2.0))
        observation["confirmed_events_total"] = len(all_events)
        observation["event_log"] = all_events
    finally:
        pubsub.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "experiment": "external-eventflow-live-worker-manual-dispatch-03A",
        "upstream_repository": UPSTREAM_REPO,
        "expected_upstream_sha": UPSTREAM_SHA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "pinned external educational demo; disposable PostgreSQL/Redis; separate actual Celery worker; explicit manual reenqueue, NOT ACK loss or worker crash",
        "observation": {},
    }
    try:
        exercise(report["observation"])
        status, reason = classify(report["observation"])
    except Exception as error:
        status, reason = "INCONCLUSIVE", "probe_exception"
        report["error_type"] = type(error).__name__
        report["error_summary"] = str(error)[:320]
        report["traceback_tail"] = traceback.format_exc()[-3000:]
    report["status"] = status
    report["reason"] = reason
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PPA EVENTFLOW LIVE WORKER PROBE:", status, "-", reason)
    # Exit 0 only for the expected, independently observed RED baseline.
    return 0 if status == "OBSERVED_RED" else 2


if __name__ == "__main__":
    sys.exit(main())
