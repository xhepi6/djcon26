"""
Show index sizes and run EXPLAIN ANALYZE for each query pattern.

Usage:
    python manage.py debug_indexes
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from shortener.queries import (
    explain,
    find_by_date_range,
    find_by_domain,
    find_by_url,
    find_unused,
    resolve,
)


class Command(BaseCommand):
    help = "Show index sizes and query plans for all index types"

    def handle(self, *args, **options):
        self.show_index_sizes()
        self.stdout.write("")

        self.section("1. Covering Index (key lookup)")
        self.stdout.write("Query: resolve('abc123')")
        from shortener.models import ShortUrl
        qs = ShortUrl.objects.filter(key="abc123").values_list("url", flat=True)
        self.stdout.write(explain(qs))

        self.section("2. Function-Based Index (domain search)")
        self.stdout.write("Query: find_by_domain('example.com')")
        self.stdout.write(explain(find_by_domain("example.com")))

        self.section("3. Partial Index (unused keys)")
        self.stdout.write("Query: find_unused()")
        self.stdout.write(explain(find_unused()))

        self.section("4. Hash Index (reverse URL lookup)")
        self.stdout.write("Query: find_by_url('https://example.com/blog/post-1')")
        self.stdout.write(explain(find_by_url("https://example.com/blog/post-1")))

        self.section("5. BRIN Index (date range)")
        end = timezone.now()
        start = end - timedelta(days=30)
        self.stdout.write(f"Query: find_by_date_range({start.date()}, {end.date()})")
        self.stdout.write(explain(find_by_date_range(start, end)))

    def section(self, title):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n--- {title} ---"))

    def show_index_sizes(self):
        self.section("Index Sizes")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) AS size
                FROM pg_indexes
                WHERE tablename = 'shortener_shorturl'
                ORDER BY pg_relation_size(indexname::regclass) DESC;
            """)
            rows = cursor.fetchall()
            if not rows:
                self.stdout.write("No indexes found. Run migrations first.")
                return
            self.stdout.write(f"{'Index':<50} {'Size':>10}")
            self.stdout.write("-" * 62)
            for name, size in rows:
                self.stdout.write(f"{name:<50} {size:>10}")
