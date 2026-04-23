"""
Seed the partitioned table with realistic workflow-step data.

Why raw SQL instead of ``WorkflowStep.objects.create(...)``? Because the
``id`` column is a Postgres IDENTITY sequence, and as of Django 5.2 a
``CompositePrimaryKey`` whose component is a ``BigIntegerField`` won't
let Django skip the ``id`` in the INSERT so the DB default fires. Raw
SQL gives us exactly the INSERT we want, and it highlights one of the
"leaky abstraction" moments the talk calls out.

Reads via the ORM in demo_orm/demo_pruning work fine — composite PKs
are transparent to SELECT.
"""

import random
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.db import connection

from workflows.models import WorkflowStep


# Months that match the partitions created in migration 0001. One row
# outside all explicit ranges lands in the DEFAULT partition on purpose.
MONTHS = [
    (2025, 11),
    (2025, 12),
    (2026, 1),
    (2026, 2),
    (2026, 3),
    (2026, 4),
    (2026, 5),
]
ROWS_PER_MONTH = 500
STATUSES = ["pending", "running", "done", "failed"]
STEP_NAMES = [
    "validate_meter",
    "read_consumption",
    "apply_tariff",
    "generate_invoice",
    "charge_payment",
    "send_receipt",
]


class Command(BaseCommand):
    help = "Insert a few thousand rows spread across every partition."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="TRUNCATE before seeding. Fast because each partition is its own table.",
        )

    def handle(self, *args, **options):
        rng = random.Random(42)

        if options["reset"]:
            # TRUNCATE on a partitioned table cascades to all partitions.
            # Much faster than DELETE FROM — this is one of the operational
            # wins of partitioning.
            with connection.cursor() as cur:
                cur.execute("TRUNCATE workflows_workflowstep;")
            self.stdout.write("truncated.")

        rows = []
        for year, month in MONTHS:
            for _ in range(ROWS_PER_MONTH):
                day = rng.randint(1, 28)
                hour = rng.randint(0, 23)
                created = datetime(year, month, day, hour, tzinfo=timezone.utc)
                completed = created + timedelta(minutes=rng.randint(1, 240))
                rows.append(
                    (
                        rng.randint(1, 50),             # workflow_id
                        rng.choice(STEP_NAMES),          # name
                        rng.choice(STATUSES),            # status
                        '{}',                            # payload
                        created,                         # created_at
                        completed,                       # completed_at
                    )
                )

        # One row in 2027 — falls outside every monthly partition and
        # ends up in workflows_workflowstep_default. Show the impact with
        # `show_partitions`.
        rows.append(
            (
                99,
                "future_step",
                "pending",
                '{}',
                datetime(2027, 1, 15, tzinfo=timezone.utc),
                None,
            )
        )

        with connection.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO workflows_workflowstep
                    (workflow_id, name, status, payload, created_at, completed_at)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s);
                """,
                rows,
            )

        total = WorkflowStep.objects.count()
        self.stdout.write(self.style.SUCCESS(f"inserted {len(rows)} rows (table now has {total})."))
        self.stdout.write("run `python manage.py show_partitions` to see the distribution.")
