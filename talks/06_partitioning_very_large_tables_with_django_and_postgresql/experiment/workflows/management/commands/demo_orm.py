"""
Show that the Django ORM works transparently against a partitioned table:
querying, aggregating, ordering, .values() — all just work. You don't
write any partition-aware code on the read path.

The one ORM gotcha to call out is on the write path: because ``id`` is
a composite-PK component backed by a Postgres IDENTITY sequence, plain
``WorkflowStep.objects.create(...)`` can't skip the id column in the
INSERT. See seed_data.py for the raw-SQL workaround.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from workflows.models import WorkflowStep


class Command(BaseCommand):
    help = "Run regular ORM queries against the partitioned table."

    def handle(self, *args, **options):
        total = WorkflowStep.objects.count()
        self.stdout.write(f"total rows: {total}")

        self.stdout.write("\nrows per status:")
        counts = (
            WorkflowStep.objects
            .values("status")
            .annotate(n=Count("id"))
            .order_by("-n")
        )
        for row in counts:
            self.stdout.write(f"  {row['status']:<10} {row['n']}")

        self.stdout.write("\nfirst 3 steps by created_at:")
        for step in WorkflowStep.objects.order_by("created_at")[:3]:
            self.stdout.write(
                f"  #{step.id}  {step.created_at.isoformat()}  "
                f"{step.name:<20} {step.status}"
            )

        self.stdout.write(
            "\nAll of the above is routed through the partition parent. "
            "Postgres picks the right partition(s) — Django never sees them."
        )
