"""
Demo: transfer using Django's built-in atomic().

Watch the SQL output — you'll see SAVEPOINT/RELEASE SAVEPOINT queries
from the nested atomic() blocks, even though no partial rollback is needed.
"""

import logging
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import reset_queries

from banking.models import Account
from banking.services import transfer_with_atomic


class Command(BaseCommand):
    help = "Run a transfer using atomic() and show all SQL queries"

    def handle(self, *args, **options):
        # Enable SQL logging so every query prints to the console
        logger = logging.getLogger("django.db.backends")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("  SQL: %(message)s"))
        logger.addHandler(handler)

        # Reset balances for a clean demo
        Account.objects.filter(name="Alice").update(balance=Decimal("1000.00"))
        Account.objects.filter(name="Bob").update(balance=Decimal("500.00"))
        reset_queries()

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=== Transfer with atomic() ==="))
        self.stdout.write("Alice sends $200 to Bob")
        self.stdout.write("Watch for SAVEPOINT queries from nested atomic() blocks:")
        self.stdout.write("")

        log = transfer_with_atomic("Alice", "Bob", Decimal("200.00"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Transfer complete: {log}"))

        # Show final balances
        alice = Account.objects.get(name="Alice")
        bob = Account.objects.get(name="Bob")
        self.stdout.write(f"  Alice: ${alice.balance}")
        self.stdout.write(f"  Bob:   ${bob.balance}")
        self.stdout.write("")
        self.stdout.write(
            "Notice the SAVEPOINT/RELEASE SAVEPOINT pairs — those are unnecessary "
            "queries created by nested atomic() blocks."
        )
