"""
Query functions from the talk. Each one demonstrates a different index.

Use the Django shell to experiment:
    python manage.py shell
    from shortener.queries import *
"""

from django.db.models import F, Func
from django.db.models.query import QuerySet

from .models import ShortUrl


# --- 1. Lookup by key (uses covering index → index-only scan) ---

def resolve(key: str) -> str | None:
    """Resolve a short key to its URL. Only fetches the URL field."""
    return (
        ShortUrl.objects
        .filter(key=key)
        .values_list("url", flat=True)
        .first()
    )


# --- 2. Find by domain (uses function-based index) ---

def find_by_domain(domain: str) -> QuerySet[ShortUrl]:
    """Find all short URLs pointing to a specific domain."""
    return ShortUrl.objects.alias(
        domain=Func(
            F("url"),
            function="SUBSTRING",
            template="%(function)s(%(expressions)s from '.*://([^/]*)')",
        ),
    ).filter(domain=domain)


# --- 3. Find unused keys (uses partial index) ---

def find_unused() -> QuerySet[ShortUrl]:
    """Find short URLs that have never been clicked."""
    return ShortUrl.objects.filter(hits=0)


# --- 4. Reverse lookup (uses hash index) ---

def find_by_url(url: str) -> QuerySet[ShortUrl]:
    """Find all short URLs pointing to an exact URL."""
    return ShortUrl.objects.filter(url=url)


# --- 5. Range search (uses BRIN index) ---

def find_by_date_range(start, end) -> QuerySet[ShortUrl]:
    """Find short URLs created in a date range."""
    return ShortUrl.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
    )


# --- Helper: show the execution plan for any queryset ---

def explain(qs: QuerySet) -> str:
    """Print EXPLAIN ANALYZE for a queryset."""
    return qs.explain(analyze=True)
