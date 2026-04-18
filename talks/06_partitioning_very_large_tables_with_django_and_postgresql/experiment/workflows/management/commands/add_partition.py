"""
Add a new monthly partition. In production this is the kind of thing you
automate with cron or pg_partman; here it's a single command so you can
feel the shape of the operation.

    python manage.py add_partition 2026-06
"""

import re
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


class Command(BaseCommand):
    help = "Create a monthly partition for a given YYYY-MM."

    def add_arguments(self, parser):
        parser.add_argument("month", help="YYYY-MM, e.g. 2026-06")

    def handle(self, *args, **options):
        match = MONTH_RE.match(options["month"])
        if not match:
            raise CommandError("month must look like YYYY-MM")

        year, month = int(match.group(1)), int(match.group(2))
        ny, nm = _next_month(year, month)
        suffix = f"{year:04d}_{month:02d}"
        lo = date(year, month, 1).isoformat()
        hi = date(ny, nm, 1).isoformat()
        name = f"workflows_workflowstep_{suffix}"

        # Using DDL + a named partition that we know doesn't yet exist.
        # CREATE TABLE ... PARTITION OF takes an exclusive lock on the
        # parent for the duration of the CREATE — brief in practice.
        sql = (
            f"CREATE TABLE {name} PARTITION OF workflows_workflowstep "
            f"FOR VALUES FROM ('{lo}') TO ('{hi}');"
        )
        with connection.cursor() as cur:
            cur.execute(sql)

        self.stdout.write(self.style.SUCCESS(
            f"created {name}  (FROM {lo} TO {hi})"
        ))
        self.stdout.write(
            "Tip: if any rows for this range were already in the DEFAULT "
            "partition, the CREATE would have failed. In that case, detach "
            "DEFAULT, move the matching rows, then attach the new partition."
        )
