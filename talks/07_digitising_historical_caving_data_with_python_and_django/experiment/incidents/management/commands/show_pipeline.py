"""
Print a compact dashboard of the pipeline state: for each incident, show
the outcome of every registered operation plus the final structured
fields. Green ✓ = success, red ✗ = failed, dash = skipped, blank = not
attempted yet.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from incidents.models import Incident, OperationRun, OperationStatus
from incidents.operations import get_registry


SYMBOL = {
    OperationStatus.SUCCESS: "✓",
    OperationStatus.FAILED:  "✗",
    OperationStatus.SKIPPED: "-",
}


class Command(BaseCommand):
    help = "Show pipeline status per incident (one row per incident, one column per op)."

    def handle(self, *args, **options):
        registry = get_registry()
        op_names = [o.name() for o in registry]

        # Prefetch all runs to avoid per-incident queries.
        runs = OperationRun.objects.all()
        status_map: dict[tuple[int, str], str] = {}
        for r in runs:
            status_map[(r.incident_id, r.operation_name)] = r.status

        header_ops = "  ".join(f"{name[:8]:>8}" for name in op_names)
        self.stdout.write(f"{'id':>3}  {header_ops}   severity   when              where")
        self.stdout.write("-" * (12 + len(header_ops) + 60))

        for incident in Incident.objects.select_related("location").order_by("id"):
            cells = []
            for name in op_names:
                status = status_map.get((incident.id, name), "")
                cells.append(f"{SYMBOL.get(status, ' '):>8}")

            when = str(incident.occurred_at) if incident.occurred_at else "—"
            where = str(incident.location) if incident.location else "—"
            self.stdout.write(
                f"{incident.id:>3}  {'  '.join(cells)}   "
                f"{incident.severity:<10} {when:<17} {where}"
            )

        # Summary of the FAILED ones so they stand out.
        failed = OperationRun.objects.filter(status=OperationStatus.FAILED).order_by(
            "incident_id", "operation_name"
        )
        if failed.exists():
            self.stdout.write("\nFailures (what the critic caught):")
            for run in failed:
                self.stdout.write(
                    f"  #{run.incident_id:<3} {run.operation_name:<20} {run.error_message}"
                )
