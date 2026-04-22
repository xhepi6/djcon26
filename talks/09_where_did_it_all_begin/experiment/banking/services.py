"""
Transfer logic implemented two ways:
1. Using Django's built-in atomic() — the "before" approach
2. Using django-subatomic — the "after" approach

Run the management commands to see the SQL difference.
"""

from decimal import Decimal

from django.db import transaction

from django_subatomic import db

from .models import Account, TransferLog


# ---------------------------------------------------------------------------
# Approach 1: Using atomic() (Django built-in)
#
# Every function wraps itself in atomic(). When nested, the inner blocks
# create savepoints — even when you don't need partial rollback.
# ---------------------------------------------------------------------------


def transfer_with_atomic(from_name: str, to_name: str, amount: Decimal) -> TransferLog:
    """Top-level transfer using atomic(). Nests with debit/credit helpers."""
    with transaction.atomic():
        from_acct = Account.objects.select_for_update().get(name=from_name)
        to_acct = Account.objects.select_for_update().get(name=to_name)

        # Each of these creates a SAVEPOINT inside the outer atomic()
        debit_with_atomic(from_acct, amount)
        credit_with_atomic(to_acct, amount)

        log = TransferLog.objects.create(
            from_account=from_acct, to_account=to_acct, amount=amount
        )
    return log


def debit_with_atomic(account: Account, amount: Decimal) -> None:
    """Debit wrapped in atomic(). Creates a savepoint when nested."""
    with transaction.atomic():
        if account.balance < amount:
            raise ValueError(f"Insufficient funds in {account.name}")
        account.balance -= amount
        account.save()


def credit_with_atomic(account: Account, amount: Decimal) -> None:
    """Credit wrapped in atomic(). Creates a savepoint when nested."""
    with transaction.atomic():
        account.balance += amount
        account.save()


# ---------------------------------------------------------------------------
# Approach 2: Using django-subatomic
#
# transaction() at the top, transaction_required() in helpers.
# No savepoints unless you explicitly ask for one.
# ---------------------------------------------------------------------------


def transfer_with_subatomic(from_name: str, to_name: str, amount: Decimal) -> TransferLog:
    """Top-level transfer using subatomic. Only one transaction, no savepoints."""
    with db.transaction():
        from_acct = Account.objects.select_for_update().get(name=from_name)
        to_acct = Account.objects.select_for_update().get(name=to_name)

        # These assert a transaction exists — no extra SQL
        debit_with_subatomic(from_acct, amount)
        credit_with_subatomic(to_acct, amount)

        log = TransferLog.objects.create(
            from_account=from_acct, to_account=to_acct, amount=amount
        )
    return log


@db.transaction_required
def debit_with_subatomic(account: Account, amount: Decimal) -> None:
    """Debit that requires a transaction. Creates no savepoint."""
    if account.balance < amount:
        raise ValueError(f"Insufficient funds in {account.name}")
    account.balance -= amount
    account.save()


@db.transaction_required
def credit_with_subatomic(account: Account, amount: Decimal) -> None:
    """Credit that requires a transaction. Creates no savepoint."""
    account.balance += amount
    account.save()


# ---------------------------------------------------------------------------
# Bonus: Using savepoint() explicitly for partial rollback
# ---------------------------------------------------------------------------


def transfer_with_bonus(from_name: str, to_name: str, amount: Decimal) -> TransferLog:
    """Transfer that tries to apply a bonus, but continues without it."""
    with db.transaction():
        from_acct = Account.objects.select_for_update().get(name=from_name)
        to_acct = Account.objects.select_for_update().get(name=to_name)

        debit_with_subatomic(from_acct, amount)
        credit_with_subatomic(to_acct, amount)

        # Savepoint only where we actually want partial rollback
        try:
            with db.savepoint():
                apply_loyalty_bonus(to_acct, amount)
        except ValueError:
            pass  # bonus failed, but the transfer still commits

        log = TransferLog.objects.create(
            from_account=from_acct, to_account=to_acct, amount=amount
        )
    return log


@db.transaction_required
def apply_loyalty_bonus(account: Account, transfer_amount: Decimal) -> None:
    """Apply 10% bonus on transfers over $500. Raises on small transfers."""
    if transfer_amount < Decimal("500"):
        raise ValueError("Transfer too small for loyalty bonus")
    bonus = transfer_amount * Decimal("0.10")
    account.balance += bonus
    account.save()
