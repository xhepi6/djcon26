"""
Multi-DB tests.

These use ``TransactionTestCase`` (not ``TestCase``) because our replica
alias uses ``TEST.MIRROR`` in settings — and MIRROR depends on Django
running real transactions per test. The primary test DB is named in
``databases``; the replica is mirrored to it automatically.

Django 5.2 is required for ``serialized_rollback`` + ``MIRROR`` to
cooperate (Django ticket #35967 fix).
"""

from django.contrib.contenttypes.models import ContentType
from django.db import connections, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from scaling.helpers import replica_aware_get_or_create
from scaling.models import Author, MainModel, Revision


class RouterTests(TransactionTestCase):
    databases = {"default", "replica"}

    def test_writes_go_to_primary(self):
        Author.objects.create(name="Tester")
        self.assertEqual(Author.objects.using("default").count(), 1)

    def test_reads_inside_atomic_use_primary(self):
        """Read-your-own-writes fix: the router routes reads to default
        whenever we're inside transaction.atomic()."""
        Author.objects.create(name="Before-tx")
        with transaction.atomic():
            Author.objects.create(name="Inside-tx")
            # If this were served by the replica it would return 1 (or 0).
            self.assertEqual(Author.objects.count(), 2)


class ReplicaAwareGetOrCreateTests(TransactionTestCase):
    databases = {"default", "replica"}

    def test_happy_path_uses_replica(self):
        Author.objects.create(name="Jake")

        with (
            CaptureQueriesContext(connections["default"]) as primary_q,
            CaptureQueriesContext(connections["replica"]) as replica_q,
        ):
            author, created = replica_aware_get_or_create(Author.objects, name="Jake")

        self.assertFalse(created)
        self.assertEqual(author.name, "Jake")
        # Under MIRROR both connections point at the same file; we only care
        # about Django's *intent*, so we check that the read used the replica
        # alias rather than the write connection.
        self.assertGreaterEqual(len(replica_q), 1)

    def test_unhappy_path_falls_back_to_primary(self):
        with CaptureQueriesContext(connections["default"]) as primary_q:
            author, created = replica_aware_get_or_create(Author.objects, name="New")
        self.assertTrue(created)
        # The fallback get_or_create must have run at least one write.
        inserts = [q for q in primary_q.captured_queries if "INSERT" in q["sql"].upper()]
        self.assertTrue(inserts, "expected an INSERT on primary during fallback")


class GenericRelationRoutingTests(TransactionTestCase):
    """Reproduces Jake's bug report for Django ticket #36389.

    Lifted from https://github.com/RealOrangeOne/django-generic-relation-db-repro.
    The PrimaryReplicaRouter must force GFK-using models to the default
    connection so that ``.update()`` on a GenericRelation doesn't leak a
    write to the replica.
    """

    databases = "__all__"

    def setUp(self):
        revision = Revision.objects.create()
        MainModel.objects.create(
            content_type=ContentType.objects.get_for_model(Revision),
            object_id=str(revision.id),
        )
        self.revision = Revision.objects.first()

    def test_no_writes_on_replica_for_generic_relation_update(self):
        with CaptureQueriesContext(connections["replica"]) as replica_queries:
            self.revision.mains.update(text="test")

        # On a real primary/replica, writes on the replica connection would
        # be rejected. The smart router prevents the bug by forcing GFK
        # models to default.
        self.assertEqual(
            replica_queries.captured_queries,
            [],
            "writes leaked onto the replica connection — ticket #36389",
        )
