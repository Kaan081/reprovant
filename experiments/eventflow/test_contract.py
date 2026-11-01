"""External acceptance contract for upstream eventflow @ pinned SHA.

Run against a disposable, real PostgreSQL Django test database. Upstream code
is imported, not copied or changed. This file is NOT a customer application.
"""
import pytest

from orders.models import Order
from orders.tasks import process_new_order

pytestmark = pytest.mark.django_db


def _record_events(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "orders.tasks.publish_event",
        lambda event_type, payload: calls.append((event_type, payload)),
    )
    return calls


def test_control_pending_can_be_confirmed(monkeypatch):
    """Control must pass or other failures are inconclusive."""
    calls = _record_events(monkeypatch)
    order = Order.objects.create(customer_email="synthetic@example.invalid", amount_cents=5000)
    process_new_order.run(order.pk)
    order.refresh_from_db()
    assert order.status == Order.Status.CONFIRMED
    assert len(calls) == 1 and calls[0][0] == "order.confirmed"


def test_contract_shipped_must_not_regress(monkeypatch):
    """A terminal shipped order must not be moved back to confirmed by replay."""
    calls = _record_events(monkeypatch)
    order = Order.objects.create(
        customer_email="synthetic@example.invalid",
        amount_cents=5000,
        status=Order.Status.SHIPPED,
    )
    process_new_order.run(order.pk)
    order.refresh_from_db()
    assert order.status == Order.Status.SHIPPED, (
        f"terminal state regressed: expected shipped, got {order.status}"
    )
    assert calls == [], "already-shipped order emitted an additional event"


def test_contract_confirmed_replay_emits_no_duplicate_event(monkeypatch):
    """Re-delivery must not emit another order.confirmed notification."""
    calls = _record_events(monkeypatch)
    order = Order.objects.create(
        customer_email="synthetic@example.invalid",
        amount_cents=5000,
        status=Order.Status.CONFIRMED,
    )
    process_new_order.run(order.pk)
    order.refresh_from_db()
    assert order.status == Order.Status.CONFIRMED
    assert calls == [], "confirmed order replay emitted a duplicate event"
