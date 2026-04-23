"""
The core demonstration: partition pruning.

Run the same logical query two ways:

  * WITH a filter on ``created_at`` (the partition key) → Postgres's
    planner eliminates 8 of the 9 partitions before execution. ``EXPLAIN``
    shows only the matching partition being scanned.

  * WITHOUT a filter on the partition key → Postgres must scan every
    partition. ``EXPLAIN`` lists ``Append`` over all children.

Both queries use the Django ORM — partitioning is transparent to the
ORM, which is the whole point of PG's native partitioning.
"""

from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import connection

from workflows.models import WorkflowStep


class Command(BaseCommand):
    help = "Show partition pruning by EXPLAINing a query with and without the partition key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-partition-key",
            action="store_true",
            help="Omit the created_at filter so pruning cannot happen.",
        )

    def handle(self, *args, **options):
        if options["no_partition_key"]:
            # Filter on workflow_id only. The planner has no way to tell
            # which partitions can contain matching rows, so it scans them
            # all.
            qs = WorkflowStep.objects.filter(workflow_id=7)
            self.stdout.write(self.style.HTTP_INFO(
                "Query: WorkflowStep.objects.filter(workflow_id=7)"
            ))
        else:
            # created_at BETWEEN a specific range inside one partition.
            # The planner computes ranges against each partition's bounds
            # and prunes the ones that can't match.
            start = datetime(2026, 3, 1, tzinfo=timezone.utc)
            end = datetime(2026, 4, 1, tzinfo=timezone.utc)
            qs = WorkflowStep.objects.filter(
                created_at__gte=start,
                created_at__lt=end,
                workflow_id=7,
            )
            self.stdout.write(self.style.HTTP_INFO(
                "Query: filter(created_at__gte=2026-03-01, "
                "created_at__lt=2026-04-01, workflow_id=7)"
            ))

        sql, params = qs.query.sql_with_params()
        self.stdout.write("\n-- SQL --")
        self.stdout.write(str(qs.query))

        with connection.cursor() as cur:
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, SUMMARY OFF) {sql}", params)
            plan = "\n".join(row[0] for row in cur.fetchall())

        self.stdout.write("\n-- EXPLAIN ANALYZE --")
        self.stdout.write(plan)

        self.stdout.write("\n-- Result count --")
        self.stdout.write(f"{qs.count()} rows")

        if options["no_partition_key"]:
            self.stdout.write("\nHint: rerun without --no-partition-key to see pruning in action.")
        else:
            self.stdout.write("\nHint: rerun with --no-partition-key to see every partition scanned.")
