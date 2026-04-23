"""
Simulate a replica catching up.

Real databases replicate over the wire; here we just copy the primary
SQLite file over the replica file. Close both connections first to
release any open file handles / journal files.
"""

import shutil

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Copy primary.sqlite3 -> replica.sqlite3 to simulate replication."

    def handle(self, *args, **options):
        connections["default"].close()
        connections["replica"].close()
        primary = settings.DATABASES["default"]["NAME"]
        replica = settings.DATABASES["replica"]["NAME"]
        shutil.copy(primary, replica)
        # Also copy the WAL file if present, so the replica sees identical state.
        for suffix in ("-wal", "-shm"):
            src = str(primary) + suffix
            dst = str(replica) + suffix
            try:
                shutil.copy(src, dst)
            except FileNotFoundError:
                pass
        self.stdout.write(self.style.SUCCESS(f"synced: {primary.name} -> {replica.name}"))
