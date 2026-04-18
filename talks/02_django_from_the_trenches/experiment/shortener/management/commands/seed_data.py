"""
Generate sample data to experiment with indexes.

Usage:
    python manage.py seed_data          # 10,000 rows (default)
    python manage.py seed_data 100000   # 100,000 rows
"""

import random
import string
from datetime import timedelta

from django.core.management.base import BaseCommand
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
        self.stdout.write(f"Creating {count} short URLs...")

        now = timezone.now()
        batch = []

        for i in range(count):
            key = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
            domain = random.choice(DOMAINS)
            path = random.choice(PATHS)
            url = f"https://{domain}{path}"
            hits = 0 if random.random() < 0.3 else random.randint(1, 10000)
            created_at = now - timedelta(days=random.randint(0, 365))

            batch.append(ShortUrl(
                key=key, url=url, hits=hits, created_at=created_at,
            ))

            if len(batch) >= 1000:
                ShortUrl.objects.bulk_create(batch, ignore_conflicts=True)
                batch = []

        if batch:
            ShortUrl.objects.bulk_create(batch, ignore_conflicts=True)

        total = ShortUrl.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Done. {total} short URLs in database."))
