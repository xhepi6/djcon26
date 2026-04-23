"""
Demo #3 — Django ticket #36389.

``instance.generic_relation.update(...)`` is a write, but the ORM routes
it through the **read** connection. On a real primary/replica setup
that means the replica receives a write and crashes (read-only).

The ``NaiveRouter`` exhibits the bug: after calling
``revision.mains.update(text=...)`` we see a write query land on the
replica connection. The ``PrimaryReplicaRouter`` walks the model
registry at startup, finds models with ``GenericForeignKey`` or
``GenericRelation``, and forces them to ``default`` — so the update
lands on the primary, as it should.

Run::

    ROUTER=naive python manage.py demo_gfk_bug
    python manage.py demo_gfk_bug
"""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections
from django.test.utils import CaptureQueriesContext

from scaling.models import MainModel, Revision


class Command(BaseCommand):
    help = "Reproduce Django ticket #36389 and show the smart-router workaround."

    def handle(self, *args, **options):
        router = settings.DATABASE_ROUTERS[0].rsplit(".", 1)[-1]
        self.stdout.write(self.style.NOTICE(f"router: {router}"))

        # Fresh state on the primary.
        MainModel.objects.using("default").all().delete()
        Revision.objects.using("default").all().delete()

        revision = Revision.objects.using("default").create()
        MainModel.objects.using("default").create(
            content_type=ContentType.objects.db_manager("default").get_for_model(Revision),
            object_id=str(revision.id),
        )
        call_command("sync_replica")

        # Refresh through the router (will end up on replica under both routers,
        # except that the smart router forces GFK models to default).
        fetched = Revision.objects.first()
        self.stdout.write(f"revision loaded from: {fetched._state.db}")

        # The bug — capturing queries on each connection to see where .update() ran.
        with (
            CaptureQueriesContext(connections["default"]) as primary_q,
            CaptureQueriesContext(connections["replica"]) as replica_q,
        ):
            fetched.mains.update(text="updated-from-demo")

        self.stdout.write(
            f"mains.update(): primary_queries={len(primary_q)}, "
            f"replica_queries={len(replica_q)}"
        )
        if len(replica_q) > 0:
            self.stdout.write(
                self.style.ERROR(
                    "BUG: a write query just landed on the REPLICA connection "
                    "(this is Django ticket #36389). On a real replica the "
                    "database would reject this as a read-only transaction."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "FIXED: the smart router detected a GFK model and pinned it "
                    "to the primary. No write leaked to the replica."
                )
            )
