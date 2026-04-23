"""
Test panel API for Talk 06: Partitioning Very Large Tables.

Provides JSON endpoints for the interactive /test/ page. Separated from
the workflows app so that module stays clean.
"""

import json
from datetime import datetime, timezone

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from workflows.models import WorkflowStep


# ---- Partition metadata ----

LIST_PARTITIONS_SQL = """
SELECT
    c.relname                                     AS partition,
    pg_get_expr(c.relpartbound, c.oid)            AS bounds,
    (SELECT reltuples FROM pg_class WHERE oid = c.oid) AS approx_rows,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_inherits i
JOIN pg_class parent    ON i.inhparent = parent.oid
JOIN pg_class c         ON i.inhrelid  = c.oid
WHERE parent.relname = 'workflows_workflowstep'
ORDER BY c.relname;
"""


def partitions_view(request):
    """Return partition list with row counts and sizes."""
    with connection.cursor() as cur:
        cur.execute("ANALYZE workflows_workflowstep;")
        cur.execute(LIST_PARTITIONS_SQL)
        rows = cur.fetchall()

    partitions = []
    for name, bounds, approx, size in rows:
        partitions.append({
            "name": name,
            "bounds": bounds or "",
            "approx_rows": int(approx or 0),
            "total_size": size,
        })
    return JsonResponse({"partitions": partitions})


# ---- Partition pruning demo ----

def pruning_view(request):
    """
    Run EXPLAIN ANALYZE on a query with and without partition key.
    Returns the query SQL and the EXPLAIN output for both cases.
    """
    results = {}

    # With partition key (pruning happens)
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2026, 4, 1, tzinfo=timezone.utc)
    qs_with = WorkflowStep.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
        workflow_id=7,
    )
    sql_with, params_with = qs_with.query.sql_with_params()

    with connection.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, COSTS OFF, SUMMARY OFF) {sql_with}", params_with)
        plan_with = [row[0] for row in cur.fetchall()]

    results["with_key"] = {
        "label": "filter(created_at__gte=2026-03-01, created_at__lt=2026-04-01, workflow_id=7)",
        "sql": str(qs_with.query),
        "plan": plan_with,
        "count": qs_with.count(),
    }

    # Without partition key (no pruning)
    qs_without = WorkflowStep.objects.filter(workflow_id=7)
    sql_without, params_without = qs_without.query.sql_with_params()

    with connection.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, COSTS OFF, SUMMARY OFF) {sql_without}", params_without)
        plan_without = [row[0] for row in cur.fetchall()]

    results["without_key"] = {
        "label": "filter(workflow_id=7)",
        "sql": str(qs_without.query),
        "plan": plan_without,
        "count": qs_without.count(),
    }

    return JsonResponse(results)


# ---- ORM demo ----

def orm_view(request):
    """Show that the Django ORM works transparently on partitioned tables."""
    from django.db.models import Count

    total = WorkflowStep.objects.count()

    # Rows per status
    status_counts = list(
        WorkflowStep.objects
        .values("status")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    # First 5 rows by date
    first_rows = []
    for step in WorkflowStep.objects.order_by("created_at")[:5]:
        first_rows.append({
            "id": step.id,
            "created_at": step.created_at.isoformat(),
            "name": step.name,
            "status": step.status,
            "workflow_id": step.workflow_id,
        })

    return JsonResponse({
        "total": total,
        "status_counts": status_counts,
        "first_rows": first_rows,
    })


# ---- Seed / reset ----

@csrf_exempt
@require_POST
def seed_view(request):
    """Truncate and re-seed the partitioned table."""
    import random

    from datetime import timedelta

    rng = random.Random(42)

    MONTHS = [
        (2025, 11), (2025, 12), (2026, 1), (2026, 2),
        (2026, 3), (2026, 4), (2026, 5),
    ]
    STATUSES = ["pending", "running", "done", "failed"]
    STEP_NAMES = [
        "validate_meter", "read_consumption", "apply_tariff",
        "generate_invoice", "charge_payment", "send_receipt",
    ]

    rows = []
    for year, month in MONTHS:
        for _ in range(500):
            day = rng.randint(1, 28)
            hour = rng.randint(0, 23)
            created = datetime(year, month, day, hour, tzinfo=timezone.utc)
            completed = created + timedelta(minutes=rng.randint(1, 240))
            rows.append((
                rng.randint(1, 50),
                rng.choice(STEP_NAMES),
                rng.choice(STATUSES),
                "{}",
                created,
                completed,
            ))

    # One future row in DEFAULT partition
    rows.append((99, "future_step", "pending", "{}", datetime(2027, 1, 15, tzinfo=timezone.utc), None))

    with connection.cursor() as cur:
        cur.execute("TRUNCATE workflows_workflowstep;")
        cur.executemany(
            """
            INSERT INTO workflows_workflowstep
                (workflow_id, name, status, payload, created_at, completed_at)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s);
            """,
            rows,
        )

    total = WorkflowStep.objects.count()
    return JsonResponse({"ok": True, "count": total})
