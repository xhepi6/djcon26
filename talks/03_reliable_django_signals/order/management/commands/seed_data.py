import random

from django.core.management.base import BaseCommand

from order.models import Order


class Command(BaseCommand):
    help = "Create sample orders with pending payments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=5, help="Number of orders to create"
        )

    def handle(self, *args, **options):
        count = options["count"]
        for _ in range(count):
            amount = random.randint(10_00, 500_00)
            order = Order.create(amount=amount)
            self.stdout.write(
                f"  Order #{order.pk} — amount={order.amount} "
                f"payment=#{order.payment_process_id} (initiated)"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCreated {count} orders. "
                f"Use 'complete_payment <id>' to simulate webhooks."
            )
        )
