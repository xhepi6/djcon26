from django.core.management.base import BaseCommand

from order.models import Order


class Command(BaseCommand):
    help = (
        "Polling fallback — find orders stuck in pending_payment "
        "whose payment has already completed, and sync them."
    )

    def handle(self, *args, **options):
        stale = Order.objects.filter(
            status="pending_payment",
            payment_process__status__in=["succeeded", "failed"],
        ).values_list("payment_process_id", flat=True)

        if not stale:
            self.stdout.write("All orders are in sync.")
            return

        for payment_process_id in stale:
            order = Order.on_payment_completed(payment_process_id=payment_process_id)
            if order:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Order #{order.pk} -> {order.status}"
                    )
                )

        self.stdout.write(f"\nSynced {len(stale)} stale order(s).")
