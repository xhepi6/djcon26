from django.db import models, transaction
from django.dispatch import receiver

import payment.signals
from payment.models import PaymentProcess


class Order(models.Model):
    """An order that depends on a PaymentProcess.

    Lifecycle: pending_payment -> completed | cancelled

    The Order never imports PaymentProcess.set_status or calls it.
    It only reacts to the payment_process_completed signal — this keeps
    the dependency one-way (order -> payment, never payment -> order).
    """

    payment_process = models.ForeignKey(PaymentProcess, on_delete=models.PROTECT)
    amount = models.BigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending_payment", "Pending Payment"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
    )

    def __str__(self):
        return f"Order #{self.pk} — {self.status} ({self.amount})"

    @classmethod
    def create(cls, *, amount: int) -> "Order":
        """Create an order with an associated payment process."""
        assert amount > 0
        with transaction.atomic():
            payment_process = PaymentProcess.create(amount=amount)
            order = cls.objects.create(
                payment_process=payment_process,
                amount=amount,
                status="pending_payment",
            )
        return order

    # -- Signal receiver -------------------------------------------------------
    # This is the decoupled handler. It's executed by the task worker, not
    # inline with the payment transaction. Failures here don't affect payment.

    @staticmethod
    @receiver(
        payment.signals.payment_process_completed,
        dispatch_uid="order.on_payment_completed",
    )
    def on_payment_completed(payment_process_id: int, **kwargs) -> "Order | None":
        """React to a payment reaching a terminal state."""
        with transaction.atomic():
            try:
                order = (
                    Order.objects.select_related("payment_process")
                    .select_for_update()
                    .get(payment_process_id=payment_process_id)
                )
            except Order.DoesNotExist:
                # Not every payment is tied to an order
                return None

            if order.status != "pending_payment":
                return order

            match order.payment_process.status:
                case "succeeded":
                    order.status = "completed"
                case "failed":
                    order.status = "cancelled"
                case _:
                    return order

            order.save()

        return order
