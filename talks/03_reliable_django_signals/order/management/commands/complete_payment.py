from django.core.management.base import BaseCommand, CommandError

from payment.models import PaymentProcess, StateError


class Command(BaseCommand):
    help = "Simulate a payment webhook — marks a payment as succeeded or failed."

    def add_arguments(self, parser):
        parser.add_argument("payment_id", type=int, help="PaymentProcess ID")
        parser.add_argument(
            "--fail",
            action="store_true",
            help="Mark the payment as failed instead of succeeded",
        )

    def handle(self, *args, **options):
        payment_id = options["payment_id"]
        succeeded = not options["fail"]

        try:
            pp = PaymentProcess.set_status(payment_id, succeeded=succeeded)
        except PaymentProcess.DoesNotExist:
            raise CommandError(f"PaymentProcess #{payment_id} not found")
        except StateError as e:
            raise CommandError(str(e))

        status_style = self.style.SUCCESS if succeeded else self.style.ERROR
        self.stdout.write(
            f"Payment #{pp.pk} -> {status_style(pp.status)}\n"
            f"\n"
            f"A task has been enqueued for the signal receiver.\n"
            f"If db_worker is running, the order will update shortly.\n"
            f"Check with: python manage.py poll_orders"
        )
