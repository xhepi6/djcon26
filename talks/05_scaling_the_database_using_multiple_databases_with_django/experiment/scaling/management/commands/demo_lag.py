"""
Demo #0 — replication lag is real.

Write to primary, immediately read from replica without syncing → the
replica doesn't see the new row yet. Run ``sync_replica``, read again,
and the row is there.

This one isn't about the router — it's about understanding the physical
setup before we look at the router-level fixes.
"""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from scaling.models import Author


class Command(BaseCommand):
    help = "Show that the replica lags the primary until we sync."

    def handle(self, *args, **options):
        router = settings.DATABASE_ROUTERS[0].rsplit(".", 1)[-1]
        self.stdout.write(self.style.NOTICE(f"router: {router}"))

        before_primary = Author.objects.using("default").count()
        before_replica = Author.objects.using("replica").count()
        self.stdout.write(f"before: primary={before_primary}, replica={before_replica}")

        Author.objects.using("default").create(name=f"Lag-Test-{before_primary}")
        mid_primary = Author.objects.using("default").count()
        mid_replica = Author.objects.using("replica").count()
        self.stdout.write(
            f"after write (no sync): primary={mid_primary}, replica={mid_replica}  "
            + ("-- replica is STALE" if mid_primary != mid_replica else "")
        )

        call_command("sync_replica")
        after_primary = Author.objects.using("default").count()
        after_replica = Author.objects.using("replica").count()
        self.stdout.write(
            self.style.SUCCESS(
                f"after sync: primary={after_primary}, replica={after_replica}"
            )
        )
