"""
ShortUrl model demonstrating various PostgreSQL index types.

Each index is labeled so you can enable/disable them to compare.
Run `python manage.py debug_indexes` to see sizes and query plans.
"""

from django.contrib.postgres.indexes import BrinIndex, HashIndex
from django.db import models
from django.db.models import F, Func, Q


class ShortUrl(models.Model):
    key = models.CharField(max_length=20)
    url = models.URLField(max_length=2048)
    hits = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # --- Covering index: key lookup returns URL without table access ---
            models.UniqueConstraint(
                fields=["key"],
                name="%(app_label)s_%(class)s_key_uk",
                include=["url"],
            ),
        ]

        indexes = [
            # --- Function-based index: extract domain via regex ---
            models.Index(
                Func(
                    F("url"),
                    function="SUBSTRING",
                    template="%(function)s(%(expressions)s from '.*://([^/]*)')",
                ),
                name="%(app_label)s_%(class)s_domain_fix",
            ),

            # --- Partial index: only rows where hits=0 ---
            models.Index(
                fields=["id"],
                condition=Q(hits=0),
                name="%(app_label)s_%(class)s_unused_pix",
            ),

            # --- Hash index: fast equality lookup on long URLs ---
            HashIndex(
                fields=["url"],
                name="%(app_label)s_%(class)s_url_hix",
            ),

            # --- BRIN index: tiny index for time-range queries ---
            BrinIndex(
                fields=("created_at",),
                pages_per_range=4,
                name="%(app_label)s_%(class)s_created_bix",
            ),
        ]

    def __str__(self):
        return f"{self.key} -> {self.url}"
