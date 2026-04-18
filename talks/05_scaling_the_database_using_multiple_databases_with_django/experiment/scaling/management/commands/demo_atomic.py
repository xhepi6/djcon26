"""
Demo #1 — the transaction / read-your-own-writes problem.

Inside ``transaction.atomic()``:

- ``NaiveRouter``: the count query goes to the replica, which can't see
  the uncommitted write. Count comes back as 0.

- ``PrimaryReplicaRouter``: ``db_for_read`` checks
  ``transaction.get_autocommit('default')`` and routes to the primary
  when we're inside a transaction, so the count is correct.

Run::

    ROUTER=naive python manage.py demo_atomic   # shows the bug
    python manage.py demo_atomic                # shows the fix
"""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from scaling.models import Author


class Command(BaseCommand):
    help = "Reads inside atomic() miss uncommitted writes unless we fix the router."

    def handle(self, *args, **options):
        router = settings.DATABASE_ROUTERS[0].rsplit(".", 1)[-1]
        self.stdout.write(self.style.NOTICE(f"router: {router}"))

        # Reset state so the demo is repeatable.
        Author.objects.using("default").filter(name__startswith="Atomic-").delete()
        call_command("sync_replica")

        baseline = Author.objects.using("default").count()
        self.stdout.write(f"baseline count on primary: {baseline}")

        with transaction.atomic():
            Author.objects.create(name="Atomic-Inside-Tx")
            # The router picks the read DB for this count:
            #   NaiveRouter -> "replica" (stale, transaction not committed yet)
            #   PrimaryReplicaRouter -> "default" (autocommit is False -> primary)
            count = Author.objects.count()
            expected = baseline + 1
            marker = "OK" if count == expected else "WRONG"
            self.stdout.write(
                self.style.SUCCESS(f"inside atomic: count={count} (expected {expected}) [{marker}]")
                if count == expected
                else self.style.ERROR(
                    f"inside atomic: count={count} (expected {expected}) [{marker}]"
                )
            )

        # After commit, any router would eventually see the new row via
        # the replica, but only after we sync.
        call_command("sync_replica")
        self.stdout.write(f"after commit + sync: count={Author.objects.count()}")
