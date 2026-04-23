"""
Test panel API for Talk 03: Reliable Django Signals.

Provides endpoints for the interactive /test/ page. Separated from app
code so the signal/payment/order modules stay clean.
"""

import json
import random

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django_tasks_db.models import DBTaskResult
from order.models import Order
from payment.models import PaymentProcess, StateError
from reliable_signal import qualname_to_callable


def state_view(request):
    """Return the full state: orders, payments, pending tasks."""
    orders = []
    for o in Order.objects.select_related("payment_process").order_by("-pk"):
        orders.append({
            "id": o.pk,
            "amount": o.amount,
            "status": o.status,
            "payment_id": o.payment_process_id,
            "payment_status": o.payment_process.status,
        })

    tasks = []
    for tr in DBTaskResult.objects.order_by("-enqueued_at")[:20]:
        kwargs = tr.args_kwargs.get("kwargs", {})
        tasks.append({
            "id": str(tr.id),
            "status": tr.status,
            "task_path": tr.task_path,
            "receiver": kwargs.get("receiver_qualname", ""),
            "payment_process_id": kwargs.get("named", {}).get("payment_process_id"),
            "enqueued_at": tr.enqueued_at.isoformat() if tr.enqueued_at else None,
            "finished_at": tr.finished_at.isoformat() if tr.finished_at else None,
        })

    return JsonResponse({"orders": orders, "tasks": tasks})


@csrf_exempt
@require_POST
def create_order_view(request):
    """Create a new order with a pending payment."""
    amount = random.randint(10_00, 500_00)
    order = Order.create(amount=amount)
    return JsonResponse({
        "ok": True,
        "order_id": order.pk,
        "payment_id": order.payment_process_id,
        "amount": order.amount,
    })


# ---------------------------------------------------------------------------
# Scenario 1: signal.send() inside transaction — receiver crashes
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def naive_crash_view(request):
    """Demonstrate signal.send() inside a transaction where the receiver fails.

    payment.save() and signal.send() are in the same atomic block.
    The receiver raises → the entire transaction rolls back.
    Payment stays "initiated" even though payment itself was valid.
    """
    data = json.loads(request.body)
    payment_id = data["payment_id"]

    try:
        pp = PaymentProcess.objects.get(id=payment_id)
    except PaymentProcess.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Payment not found"}, status=404)

    if pp.status != "initiated":
        return JsonResponse(
            {"ok": False, "error": f"Payment already '{pp.status}'"}, status=400
        )

    try:
        with transaction.atomic():
            pp.status = "succeeded"
            pp.save()

            # This is what signal.send() does: call receivers inline.
            # If a receiver crashes, the exception propagates up...
            raise Exception(
                "Receiver crashed! (e.g. email service timeout, DB error in receiver)"
            )

    except Exception as e:
        # ...and the ENTIRE transaction rolls back, including payment.save()
        pp.refresh_from_db()
        return JsonResponse({
            "ok": True,
            "rolled_back": True,
            "payment_id": payment_id,
            "payment_status": pp.status,  # still "initiated" — rolled back!
            "error": str(e),
        })


# ---------------------------------------------------------------------------
# Scenario 2: signal.send() after transaction — the gap
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def naive_gap_view(request):
    """Demonstrate the gap between commit and signal.send().

    Payment is saved and committed. Then we'd call signal.send()...
    but the server "crashes" before that happens. No signal, no task,
    no receiver. The order stays pending_payment forever.
    """
    data = json.loads(request.body)
    payment_id = data["payment_id"]

    try:
        pp = PaymentProcess.objects.get(id=payment_id)
    except PaymentProcess.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Payment not found"}, status=404)

    if pp.status != "initiated":
        return JsonResponse(
            {"ok": False, "error": f"Payment already '{pp.status}'"}, status=400
        )

    # Transaction commits — payment is saved
    with transaction.atomic():
        pp = PaymentProcess.objects.select_for_update().get(id=payment_id)
        pp.status = "succeeded"
        pp.save()
        # Note: we do NOT call send_reliable() here — no task is enqueued

    # Here is where signal.send() would happen...
    # But the server "crashes." Signal never fires. No task in the queue.
    # The order stays pending_payment forever.

    return JsonResponse({
        "ok": True,
        "crashed_in_gap": True,
        "payment_id": payment_id,
        "payment_status": "succeeded",
    })


# ---------------------------------------------------------------------------
# Scenario 3: send_reliable() — the fix (transactional outbox)
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def reliable_send_view(request):
    """Complete a payment using send_reliable() — the outbox pattern."""
    data = json.loads(request.body)
    payment_id = data["payment_id"]
    succeeded = data.get("succeeded", True)

    try:
        pp = PaymentProcess.set_status(payment_id, succeeded=succeeded)
    except PaymentProcess.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Payment not found"}, status=404)
    except StateError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    return JsonResponse({
        "ok": True,
        "payment_id": pp.pk,
        "status": pp.status,
    })


@csrf_exempt
@require_POST
def process_tasks_view(request):
    """Process all pending tasks synchronously (simulates what db_worker does)."""
    pending = DBTaskResult.objects.filter(status="READY").order_by("enqueued_at")
    processed = 0
    errors = []

    for tr in pending:
        kwargs = tr.args_kwargs.get("kwargs", {})
        receiver_qualname = kwargs.get("receiver_qualname")
        named = kwargs.get("named", {})

        try:
            receiver = qualname_to_callable(receiver_qualname)
            receiver(signal=None, sender=None, **named)
            tr.status = "SUCCESSFUL"
            tr.save()
            processed += 1
        except Exception as e:
            tr.status = "FAILED"
            tr.save()
            errors.append({"task_id": str(tr.id), "error": str(e)})

    return JsonResponse({
        "ok": True,
        "processed": processed,
        "errors": errors,
    })


@csrf_exempt
@require_POST
def poll_orders_view(request):
    """Polling fallback — sync orders whose payments already completed."""
    stale_ids = list(
        Order.objects.filter(
            status="pending_payment",
            payment_process__status__in=["succeeded", "failed"],
        ).values_list("payment_process_id", flat=True)
    )

    synced = []
    for payment_process_id in stale_ids:
        order = Order.on_payment_completed(payment_process_id=payment_process_id)
        if order:
            synced.append({"order_id": order.pk, "status": order.status})

    return JsonResponse({"ok": True, "synced": synced})


@csrf_exempt
@require_POST
def reset_view(request):
    """Delete all orders, payments, and task results."""
    Order.objects.all().delete()
    PaymentProcess.objects.all().delete()
    DBTaskResult.objects.all().delete()
    return JsonResponse({"ok": True})
