import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .events import ORDER_CONFIRMED, ORDER_FAILED, publish_event
from .models import Order

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_new_order(self, order_id: int):
    """Process only a pending order once at the database state-transition boundary.

    This narrowly guards duplicate dispatch and stale-state overwrite.
    Redis pub/sub publishing remains outside the SQL transaction: this is
    NOT an atomic outbox, exactly-once delivery, or ACK-loss guarantee.
    """
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("process_new_order: order %s no longer exists", order_id)
        return

    if order.amount_cents < settings.ORDER_MIN_VALID_AMOUNT_CENTS:
        target = Order.Status.FAILED
    else:
        target = Order.Status.CONFIRMED

    # Atomic compare-and-set in PostgreSQL: a concurrent or repeated worker
    # cannot change CONFIRMED, SHIPPED, or FAILED back from a terminal state.
    transitioned = Order.objects.filter(
        pk=order_id,
        status=Order.Status.PENDING,
    ).update(status=target, updated_at=timezone.now())

    if transitioned != 1:
        logger.info("process_new_order: skipped non-pending order %s", order_id)
        return

    if target == Order.Status.FAILED:
        publish_event(ORDER_FAILED, {"order_id": order.pk, "reason": "amount_too_low"})
    else:
        publish_event(ORDER_CONFIRMED, {"order_id": order.pk, "customer_email": order.customer_email})


@shared_task
def send_confirmation_email(order_id: int, customer_email: str):
    """Simulated notification step, triggered off `order.confirmed`."""
    logger.info("sending confirmation email for order %s to %s", order_id, customer_email)
