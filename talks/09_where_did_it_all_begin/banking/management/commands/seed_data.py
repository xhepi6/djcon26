from decimal import Decimal

from django.core.management.base import BaseCommand

from banking.models import Account, TransferLog


class Command(BaseCommand):
    help = "Create sample accounts for the transaction demo"

    def handle(self, *args, **options):
        TransferLog.objects.all().delete()
        Account.objects.all().delete()

        accounts = [
            Account(name="Alice", balance=Decimal("1000.00")),
            Account(name="Bob", balance=Decimal("500.00")),
            Account(name="Charlie", balance=Decimal("250.00")),
        ]
        Account.objects.bulk_create(accounts)

        self.stdout.write(self.style.SUCCESS("Created accounts:"))
        for acct in Account.objects.all():
            self.stdout.write(f"  {acct}")
