"""
Run the pipeline: for each incident, for each registered operation (in
registration order), check prerequisites + ``should_run``, then execute.

Every attempt writes an ``OperationRun`` row with the outcome. Re-running
is safe — operations with an existing SUCCESS or SKIPPED row are not
re-attempted unless ``--retry-failed`` or ``--rerun`` is set.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from incidents.models import Incident, OperationRun, OperationStatus
from incidents.operations import get_registry
from incidents.operations.base import Operation


def _prereqs_satisfied(incident: Incident, op: type[Operation]) -> bool:
    """True iff every class in ``op.requires`` has a SUCCESS row."""
    for required in op.requires:
        ok = OperationRun.objects.filter(
            incident=incident,
            operation_name=required.name(),
            status=OperationStatus.SUCCESS,
        ).exists()
        if not ok:
            return False
    return True


class Command(BaseCommand):
    help = "Run every registered operation against every incident."

    def add_arguments(self, parser):
        parser.add_argument(
            "--incident",
            type=int,
            help="restrict to a single incident id",
        )
        parser.add_argument(
            "--op",
            help="restrict to a single operation (class name)",
        )
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="re-attempt ops currently marked FAILED",
        )
        parser.add_argument(
            "--rerun",
            action="store_true",
            help="re-run every op from scratch (clears OperationRun rows first)",
        )

    def handle(self, *args, **options):
        incidents = Incident.objects.all().order_by("id")
        if options["incident"]:
            incidents = incidents.filter(id=options["incident"])

        registry = get_registry()
        if options["op"]:
            registry = [o for o in registry if o.name() == options["op"]]
            if not registry:
                self.stderr.write(f"no operation named {options['op']!r}")
                return

        if options["rerun"]:
            filters = {"incident__in": incidents}
            if options["op"]:
                filters["operation_name__in"] = [o.name() for o in registry]
            deleted, _ = OperationRun.objects.filter(**filters).delete()
            self.stdout.write(f"cleared {deleted} previous operation rows.")

        totals = {"success": 0, "failed": 0, "skipped": 0, "blocked": 0}

        for incident in incidents:
            for op_cls in registry:
                existing = OperationRun.objects.filter(
                    incident=incident, operation_name=op_cls.name()
                ).first()

                # Skip already-finished work unless asked to revisit.
                if existing:
                    if existing.status == OperationStatus.SUCCESS:
                        continue
                    if (
                        existing.status == OperationStatus.FAILED
                        and not options["retry_failed"]
                    ):
                        continue

                if not _prereqs_satisfied(incident, op_cls):
                    # Don't record a DB row — a blocked step should run once
                    # its prereqs succeed. Just count it for the summary.
                    totals["blocked"] += 1
                    continue

                op = op_cls()
                if not op.should_run(incident):
                    self._upsert_run(incident, op_cls, OperationStatus.SKIPPED)
                    totals["skipped"] += 1
                    continue

                try:
                    with transaction.atomic():
                        op.run(incident)
                except Exception as exc:  # noqa: BLE001 — want every error recorded
                    self._upsert_run(
                        incident, op_cls, OperationStatus.FAILED, str(exc)
                    )
                    totals["failed"] += 1
                    self.stdout.write(self.style.WARNING(
                        f"  [#{incident.id}] {op_cls.name()} FAILED: {exc}"
                    ))
                else:
                    self._upsert_run(incident, op_cls, OperationStatus.SUCCESS)
                    totals["success"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"done. success={totals['success']} failed={totals['failed']} "
            f"skipped={totals['skipped']} blocked={totals['blocked']}"
        ))

    def _upsert_run(
        self,
        incident: Incident,
        op_cls: type[Operation],
        status: OperationStatus,
        error_message: str = "",
    ) -> None:
        OperationRun.objects.update_or_create(
            incident=incident,
            operation_name=op_cls.name(),
            defaults={"status": status, "error_message": error_message},
        )
