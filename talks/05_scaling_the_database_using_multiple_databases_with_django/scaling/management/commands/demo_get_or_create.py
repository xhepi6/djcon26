"""
Demo #2 — ``get_or_create`` always hits the primary.

``Author.objects.get_or_create(name='Jake')`` runs its SELECT through the
write connection (``default``), because Django wants to guarantee
read-your-writes for it. That means even on the happy path (row exists
already) you're paying with a primary-hit.

``replica_aware_get_or_create`` tries an optimistic ``.get()`` first.
The ``.get()`` goes through ``db_for_read`` → the replica — which is the
whole point of having replicas.

We detect where each query ran by capturing queries on both connections.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections
from django.test.utils import CaptureQueriesContext

from scaling.helpers import replica_aware_get_or_create
from scaling.models import Author


class Command(BaseCommand):
    help = "Compare Model.objects.get_or_create vs replica_aware_get_or_create."

    def handle(self, *args, **options):
        # Make sure "Jake Howard" is present on the replica.
        Author.objects.using("default").get_or_create(name="Jake Howard")
        call_command("sync_replica")

        self.stdout.write(self.style.MIGRATE_HEADING("Model.objects.get_or_create:"))
        with (
            CaptureQueriesContext(connections["default"]) as primary_q,
            CaptureQueriesContext(connections["replica"]) as replica_q,
        ):
            author, created = Author.objects.get_or_create(
                name="Jake Howard", defaults={"bio": ""}
            )
        self.stdout.write(f"  created={created}, primary_queries={len(primary_q)}, replica_queries={len(replica_q)}")
        self.stdout.write("  -> get_or_create went to PRIMARY (bypassing replica)")

        self.stdout.write(self.style.MIGRATE_HEADING("replica_aware_get_or_create:"))
        with (
            CaptureQueriesContext(connections["default"]) as primary_q,
            CaptureQueriesContext(connections["replica"]) as replica_q,
        ):
            author, created = replica_aware_get_or_create(
                Author.objects, defaults={"bio": ""}, name="Jake Howard"
            )
        self.stdout.write(f"  created={created}, primary_queries={len(primary_q)}, replica_queries={len(replica_q)}")
        self.stdout.write("  -> happy path served by REPLICA (1 query)")

        self.stdout.write(self.style.MIGRATE_HEADING("unhappy path — row missing:"))
        Author.objects.using("default").filter(name="Not-Yet-Created").delete()
        call_command("sync_replica")
        with (
            CaptureQueriesContext(connections["default"]) as primary_q,
            CaptureQueriesContext(connections["replica"]) as replica_q,
        ):
            author, created = replica_aware_get_or_create(
                Author.objects, name="Not-Yet-Created"
            )
        self.stdout.write(f"  created={created}, primary_queries={len(primary_q)}, replica_queries={len(replica_q)}")
        self.stdout.write("  -> falls back to get_or_create on PRIMARY")
