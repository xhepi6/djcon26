"""
Generate sample data to experiment with indexes.

Usage:
    python manage.py seed_data          # 10,000 rows (default)
    python manage.py seed_data 100000   # 100,000 rows

Rows are inserted in chronological order so BRIN index on created_at
works (BRIN needs physical disk order to correlate with column values).
"""

import random
import string
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from shortener.models import ShortUrl


DOMAINS = [
    "example.com", "hakibenita.com", "djangoproject.com",
    "python.org", "github.com", "stackoverflow.com",
    "docs.djangoproject.com", "pypi.org", "medium.com",
    "dev.to", "reddit.com", "news.ycombinator.com",
]

PATHS = [
    "/blog/post-1", "/about", "/pricing", "/docs/getting-started",
    "/api/v2/users", "/login", "/signup", "/dashboard",
    "/settings", "/products/widget", "/faq", "/contact",
    "/?utm_source=twitter", "/?utm_source=email", "/?ref=djangocon",
]


class Command(BaseCommand):
    help = "Seed the database with sample ShortUrl data"

    def add_arguments(self, parser):
        parser.add_argument("count", nargs="?", type=int, default=10_000)

    def handle(self, *args, count, **options):
        ShortUrl.objects.all().delete()
        self.stdout.write(f"Creating {count} short URLs...")

        now = timezone.now()
        batch = []

        # Insert in chronological order so rows are physically sorted by date.
        # This is what makes BRIN indexes effective — physical order = date order.
        for i in range(count):
            key = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
            domain = random.choice(DOMAINS)
            path = random.choice(PATHS)
            url = f"https://{domain}{path}"
            hits = 0 if random.random() < 0.3 else random.randint(1, 10000)

            batch.append(ShortUrl(key=key, url=url, hits=hits))

            if len(batch) >= 1000:
                ShortUrl.objects.bulk_create(batch, ignore_conflicts=True)
                batch = []

        if batch:
            ShortUrl.objects.bulk_create(batch, ignore_conflicts=True)

        # auto_now_add prevents setting created_at directly.
        # Update via SQL to spread dates over 365 days in insertion order,
        # preserving the physical-order-matches-date-order that BRIN needs.
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (ORDER BY id DESC) AS rn,
                           COUNT(*) OVER () AS total
                    FROM shortener_shorturl
                )
                UPDATE shortener_shorturl s
                SET created_at = NOW() - (ranked.rn::double precision / ranked.total * INTERVAL '365 days')
                FROM ranked
                WHERE s.id = ranked.id;
            """)

        # Force ANALYZE so the planner sees fresh stats (including correlation)
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE shortener_shorturl;")

        total = ShortUrl.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Done. {total} short URLs in database."))
