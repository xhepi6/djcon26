"""Compare query counts: naive Django vs Mantle shapes.

This is the core demonstration of what Mantle does. Run after seed_data:
  python manage.py compare_queries
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.test.utils import CaptureQueriesContext

from mantle import Query

from bookmarks.models import Bookmark
from bookmarks.shapes import BookmarkData, BookmarkFlat, BookmarkWithUser


class Command(BaseCommand):
    help = "Show query counts: naive Django vs Mantle (proves N+1 prevention)"

    def handle(self, *args, **options):
        count = Bookmark.objects.count()
        if count == 0:
            self.stderr.write("No bookmarks. Run: python manage.py seed_data")
            return

        self.stdout.write(f"\n{count} bookmarks in database\n")

        # --- Naive: N+1 ---
        self.stdout.write("\n--- NAIVE Django (N+1 problem) ---")
        with CaptureQueriesContext(connection) as ctx:
            for b in Bookmark.objects.all():
                _ = b.user.username
        self.stdout.write(f"Queries: {len(ctx)}")
        for q in ctx:
            self.stdout.write(f"  {q['sql']}")

        # --- Mantle: BookmarkData (basic projection) ---
        self.stdout.write("\n--- Mantle: BookmarkData (fields only) ---")
        with CaptureQueriesContext(connection) as ctx:
            Query(Bookmark.objects.all(), BookmarkData).all()
        self.stdout.write(f"Queries: {len(ctx)}")
        for q in ctx:
            self.stdout.write(f"  {q['sql']}")

        # --- Mantle: BookmarkWithUser (nested, auto-prefetch) ---
        self.stdout.write("\n--- Mantle: BookmarkWithUser (nested user) ---")
        with CaptureQueriesContext(connection) as ctx:
            Query(Bookmark.objects.all(), BookmarkWithUser).all()
        self.stdout.write(f"Queries: {len(ctx)}")
        for q in ctx:
            self.stdout.write(f"  {q['sql']}")

        # --- Mantle: BookmarkFlat (@overrides, JOIN) ---
        self.stdout.write("\n--- Mantle: BookmarkFlat (flattened via JOIN) ---")
        with CaptureQueriesContext(connection) as ctx:
            Query(Bookmark.objects.all(), BookmarkFlat).all()
        self.stdout.write(f"Queries: {len(ctx)}")
        for q in ctx:
            self.stdout.write(f"  {q['sql']}")

        # --- Summary ---
        self.stdout.write("\n--- Summary ---")
        self.stdout.write(f"Naive N+1:       {count + 1} queries (1 + {count} per bookmark)")
        self.stdout.write("Mantle basic:    1 query  (only needed fields)")
        self.stdout.write("Mantle nested:   2 queries (auto-prefetch user)")
        self.stdout.write("Mantle flat:     1 query  (JOIN via @overrides)")
        self.stdout.write("")
