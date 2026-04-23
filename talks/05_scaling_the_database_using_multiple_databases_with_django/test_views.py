"""
Test panel API for Talk 05: Scaling the Database Using Multiple Databases.

Provides endpoints for the interactive /test/ page. Separated from app
code so the scaling module stays clean.

Each endpoint runs one of the demos from the talk and returns structured
JSON showing what happened -- which connection handled which queries,
whether the bug or the fix was active, etc.
"""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connections, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.test.utils import CaptureQueriesContext

from scaling.helpers import replica_aware_get_or_create
from scaling.models import Author, Book, MainModel, Revision


def state_view(request):
    """Return the current state of both databases and router info."""
    router = settings.DATABASE_ROUTERS[0].rsplit(".", 1)[-1]

    primary_authors = Author.objects.using("default").count()
    primary_books = Book.objects.using("default").count()
    replica_authors = Author.objects.using("replica").count()
    replica_books = Book.objects.using("replica").count()

    authors = list(
        Author.objects.using("default")
        .order_by("pk")
        .values("id", "name", "bio")
    )
    books = list(
        Book.objects.using("default")
        .select_related("author")
        .order_by("pk")
        .values("id", "title", "author__name")
    )

    return JsonResponse({
        "router": router,
        "primary": {"authors": primary_authors, "books": primary_books},
        "replica": {"authors": replica_authors, "books": replica_books},
        "in_sync": (primary_authors == replica_authors and primary_books == replica_books),
        "authors": authors,
        "books": books,
    })


@csrf_exempt
@require_POST
def sync_view(request):
    """Run sync_replica to simulate replication catching up."""
    call_command("sync_replica")

    primary_count = Author.objects.using("default").count()
    replica_count = Author.objects.using("replica").count()

    return JsonResponse({
        "ok": True,
        "primary_authors": primary_count,
        "replica_authors": replica_count,
        "in_sync": primary_count == replica_count,
    })


@csrf_exempt
@require_POST
def demo_lag_view(request):
    """Demo: replication lag -- write to primary, read from replica before sync.

    Shows that the replica doesn't see un-replicated data.
    """
    before_primary = Author.objects.using("default").count()
    before_replica = Author.objects.using("replica").count()

    # Write to primary only
    Author.objects.using("default").create(name=f"Lag-Test-{before_primary}")

    after_primary = Author.objects.using("default").count()
    after_replica = Author.objects.using("replica").count()

    stale = after_primary != after_replica

    # Now sync
    call_command("sync_replica")
    synced_replica = Author.objects.using("replica").count()

    return JsonResponse({
        "ok": True,
        "before": {"primary": before_primary, "replica": before_replica},
        "after_write": {"primary": after_primary, "replica": after_replica},
        "replica_was_stale": stale,
        "after_sync": {"primary": after_primary, "replica": synced_replica},
    })


@csrf_exempt
@require_POST
def demo_atomic_view(request):
    """Demo: reads inside transaction.atomic() miss uncommitted writes.

    With the naive router, count returns 0 because the read goes to the
    replica which can't see uncommitted data. The smart router detects
    the transaction and reads from primary instead.
    """
    router = settings.DATABASE_ROUTERS[0].rsplit(".", 1)[-1]

    # Clean slate
    Author.objects.using("default").filter(name__startswith="AtomicDemo-").delete()
    call_command("sync_replica")
    baseline = Author.objects.using("default").count()

    result = {}
    with transaction.atomic():
        Author.objects.create(name="AtomicDemo-Inside-Tx")

        # Capture which connection handles the count query
        with (
            CaptureQueriesContext(connections["default"]) as pq,
            CaptureQueriesContext(connections["replica"]) as rq,
        ):
            count = Author.objects.count()

        expected = baseline + 1
        result = {
            "ok": True,
            "router": router,
            "baseline": baseline,
            "count_inside_atomic": count,
            "expected": expected,
            "correct": count == expected,
            "read_from": "primary" if len(pq) > 0 else "replica",
            "primary_queries": len(pq),
            "replica_queries": len(rq),
        }

    # Cleanup
    Author.objects.using("default").filter(name__startswith="AtomicDemo-").delete()
    call_command("sync_replica")

    return JsonResponse(result)


@csrf_exempt
@require_POST
def demo_get_or_create_view(request):
    """Demo: get_or_create always hits primary vs replica_aware_get_or_create.

    Shows that the standard get_or_create routes through the write
    connection even for existing rows, while the replica-aware version
    uses the replica for the happy path.
    """
    # Ensure Jake exists on both DBs
    Author.objects.using("default").get_or_create(name="Jake Howard")
    call_command("sync_replica")

    # Standard get_or_create
    with (
        CaptureQueriesContext(connections["default"]) as std_pq,
        CaptureQueriesContext(connections["replica"]) as std_rq,
    ):
        _, std_created = Author.objects.get_or_create(
            name="Jake Howard", defaults={"bio": ""}
        )

    # replica_aware_get_or_create (happy path -- row exists)
    with (
        CaptureQueriesContext(connections["default"]) as ra_pq,
        CaptureQueriesContext(connections["replica"]) as ra_rq,
    ):
        _, ra_created = replica_aware_get_or_create(
            Author.objects, defaults={"bio": ""}, name="Jake Howard"
        )

    # Unhappy path -- row does NOT exist
    Author.objects.using("default").filter(name="GetOrCreateTest-New").delete()
    call_command("sync_replica")

    with (
        CaptureQueriesContext(connections["default"]) as unhappy_pq,
        CaptureQueriesContext(connections["replica"]) as unhappy_rq,
    ):
        _, unhappy_created = replica_aware_get_or_create(
            Author.objects, name="GetOrCreateTest-New"
        )

    # Cleanup
    Author.objects.using("default").filter(name="GetOrCreateTest-New").delete()
    call_command("sync_replica")

    return JsonResponse({
        "ok": True,
        "standard_get_or_create": {
            "created": std_created,
            "primary_queries": len(std_pq),
            "replica_queries": len(std_rq),
            "read_from": "primary (always)",
        },
        "replica_aware_happy_path": {
            "created": ra_created,
            "primary_queries": len(ra_pq),
            "replica_queries": len(ra_rq),
            "read_from": "replica" if len(ra_rq) > 0 else "primary",
        },
        "replica_aware_unhappy_path": {
            "created": unhappy_created,
            "primary_queries": len(unhappy_pq),
            "replica_queries": len(unhappy_rq),
            "note": "Falls back to primary get_or_create when row is missing",
        },
    })


@csrf_exempt
@require_POST
def demo_gfk_view(request):
    """Demo: GenericRelation .update() routes to replica (Django ticket #36389).

    The naive router lets the write leak to the replica connection. The
    smart router detects GFK models and forces them to default.
    """
    router = settings.DATABASE_ROUTERS[0].rsplit(".", 1)[-1]

    # Set up fresh test data
    MainModel.objects.using("default").all().delete()
    Revision.objects.using("default").all().delete()

    revision = Revision.objects.using("default").create()
    MainModel.objects.using("default").create(
        content_type=ContentType.objects.db_manager("default").get_for_model(Revision),
        object_id=str(revision.id),
    )
    call_command("sync_replica")

    # Fetch through the router
    fetched = Revision.objects.first()
    loaded_from = fetched._state.db

    # Capture where the .update() write goes
    with (
        CaptureQueriesContext(connections["default"]) as pq,
        CaptureQueriesContext(connections["replica"]) as rq,
    ):
        fetched.mains.update(text="updated-from-test-panel")

    write_leaked = len(rq) > 0

    # Cleanup
    MainModel.objects.using("default").all().delete()
    Revision.objects.using("default").all().delete()
    call_command("sync_replica")

    return JsonResponse({
        "ok": True,
        "router": router,
        "revision_loaded_from": loaded_from,
        "primary_queries": len(pq),
        "replica_queries": len(rq),
        "write_leaked_to_replica": write_leaked,
        "bug_active": write_leaked,
        "explanation": (
            "BUG: .update() on a GenericRelation went to the replica connection"
            if write_leaked
            else "FIXED: smart router pinned GFK models to default, write went to primary"
        ),
    })


@csrf_exempt
@require_POST
def seed_view(request):
    """Seed the database with demo data."""
    call_command("seed_data", "--reset")
    return JsonResponse({
        "ok": True,
        "authors": Author.objects.using("default").count(),
        "books": Book.objects.using("default").count(),
    })


@csrf_exempt
@require_POST
def reset_view(request):
    """Delete all data and re-seed."""
    Book.objects.using("default").all().delete()
    Author.objects.using("default").all().delete()
    MainModel.objects.using("default").all().delete()
    Revision.objects.using("default").all().delete()
    call_command("sync_replica")
    call_command("seed_data")
    return JsonResponse({
        "ok": True,
        "authors": Author.objects.using("default").count(),
        "books": Book.objects.using("default").count(),
    })
