"""
Demo: transfer using django-subatomic.

Compare with demo_atomic — no SAVEPOINT queries here.
transaction() at the top, transaction_required() in helpers.
"""

import logging
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import reset_queries

from banking.models import Account
from banking.services import transfer_with_bonus, transfer_with_subatomic


class Command(BaseCommand):
    help = "Run transfers using django-subatomic and show all SQL queries"

    def handle(self, *args, **options):
        # Enable SQL logging
        logger = logging.getLogger("django.db.backends")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("  SQL: %(message)s"))
        logger.addHandler(handler)

        # Reset balances
        Account.objects.filter(name="Alice").update(balance=Decimal("1000.00"))
        Account.objects.filter(name="Bob").update(balance=Decimal("500.00"))
        Account.objects.filter(name="Charlie").update(balance=Decimal("250.00"))
        reset_queries()

        # --- Demo 1: Clean transfer, no savepoints ---
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=== Transfer with subatomic (no savepoints) ==="))
        self.stdout.write("Alice sends $200 to Bob")
        self.stdout.write("No SAVEPOINT queries — transaction_required() adds zero SQL:")
        self.stdout.write("")

        log = transfer_with_subatomic("Alice", "Bob", Decimal("200.00"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Transfer complete: {log}"))
        alice = Account.objects.get(name="Alice")
        bob = Account.objects.get(name="Bob")
        self.stdout.write(f"  Alice: ${alice.balance}")
        self.stdout.write(f"  Bob:   ${bob.balance}")

        reset_queries()

        # --- Demo 2: Transfer with explicit savepoint for bonus ---
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=== Transfer with explicit savepoint (bonus attempt) ==="))
        self.stdout.write("Alice sends $100 to Charlie (too small for loyalty bonus)")
        self.stdout.write("Savepoint used intentionally for partial rollback:")
        self.stdout.write("")

        log = transfer_with_bonus("Alice", "Charlie", Decimal("100.00"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Transfer complete: {log}"))
        alice = Account.objects.get(name="Alice")
        charlie = Account.objects.get(name="Charlie")
        self.stdout.write(f"  Alice:   ${alice.balance}")
        self.stdout.write(f"  Charlie: ${charlie.balance}")
        self.stdout.write("")
        self.stdout.write(
            "The savepoint here was intentional — we wanted partial rollback "
            "for the bonus. Compare with demo_atomic where savepoints are accidental."
        )
