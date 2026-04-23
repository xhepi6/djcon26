"""
List every partition of ``workflows_workflowstep`` with its row count and
on-disk size. This is the "why partitioning exists" view: each partition
is its own physical table with its own indexes and vacuum cadence.
"""

from django.core.management.base import BaseCommand
from django.db import connection


# pg_inherits links partitions to their parent. pg_class.relname gives us
# the partition name; pg_total_relation_size includes indexes.
LIST_SQL = """
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


class Command(BaseCommand):
    help = "Show each child partition, its range, estimated rows and total size."

    def handle(self, *args, **options):
        with connection.cursor() as cur:
            # ANALYZE first so reltuples isn't stale.
            cur.execute("ANALYZE workflows_workflowstep;")
            cur.execute(LIST_SQL)
            rows = cur.fetchall()

        if not rows:
            self.stdout.write(self.style.WARNING(
                "no partitions found — did you run migrate?"
            ))
            return

        name_w = max(len(r[0]) for r in rows)
        bounds_w = max(len(r[1] or "") for r in rows)
        self.stdout.write(
            f"{'partition'.ljust(name_w)}  "
            f"{'bounds'.ljust(bounds_w)}  "
            f"{'~rows':>10}  size"
        )
        self.stdout.write("-" * (name_w + bounds_w + 30))
        for name, bounds, approx, size in rows:
            self.stdout.write(
                f"{name.ljust(name_w)}  "
                f"{(bounds or '').ljust(bounds_w)}  "
                f"{int(approx or 0):>10}  {size}"
            )
