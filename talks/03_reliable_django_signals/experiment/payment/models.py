from django.db import models, transaction

from payment import signals


class PaymentProcessError(Exception):
    pass


class StateError(PaymentProcessError):
    pass


class PaymentProcess(models.Model):
    """Represents a payment interaction with a third-party provider.

    Lifecycle: initiated -> succeeded | failed
    """

    amount = models.BigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("initiated", "Initiated"),
            ("succeeded", "Succeeded"),
            ("failed", "Failed"),
        ],
    )

    class Meta:
        verbose_name_plural = "payment processes"

    def __str__(self):
        return f"Payment #{self.pk} — {self.status} ({self.amount})"

    @classmethod
    def create(cls, *, amount: int) -> "PaymentProcess":
        assert amount > 0
        return cls.objects.create(amount=amount, status="initiated")

    @classmethod
    def set_status(cls, id: int, *, succeeded: bool) -> "PaymentProcess":
        """Simulate receiving a payment webhook.

        The signal is sent INSIDE the transaction — the task row is committed
        atomically with the status change. If we crash after commit, the
        worker will still pick up the task. This is the key insight.
        """
        with transaction.atomic():
            payment_process = cls.objects.select_for_update().get(id=id)

            if payment_process.status != "initiated":
                raise StateError(
                    f"Cannot transition from '{payment_process.status}'"
                )

            payment_process.status = "succeeded" if succeeded else "failed"
            payment_process.save()

            # Enqueue receiver tasks inside the transaction (outbox pattern)
            signals.payment_process_completed.send_reliable(
                sender=None,
                payment_process_id=payment_process.id,
            )

        return payment_process
