"""
Populate the database with a handful of books so the demo has something to show.

Usage::

    python manage.py seed_books
    python manage.py seed_books --show    # print all books as JSON, then exit
    python manage.py seed_books --reset   # wipe before reseeding
"""

import json

from django.core.management.base import BaseCommand

from books.models import Book


SEED = [
    {
        "title": "The Django Book",
        "author": "Adrian Holovaty",
        "year": 2009,
        "misc": {"trivia": "Co-created by the Lawrence Journal-World web team.", "notes": "classic"},
    },
    {
        "title": "Two Scoops of Django",
        "author": "Daniel & Audrey Roy Greenfeld",
        "year": 2013,
        "misc": {"trivia": "Every edition gets a new ice-cream-themed cover."},
    },
    {
        "title": "HTMX for the busy Pythonista",
        "author": "Various",
        "year": 2024,
        "misc": {},
    },
]


class Command(BaseCommand):
    help = "Seed the database with example books (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete all books first")
        parser.add_argument("--show", action="store_true", help="Print all books and exit")

    def handle(self, *args, **options):
        if options["show"]:
            self._show()
            return
        if options["reset"]:
            count, _ = Book.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"deleted {count} existing rows"))
        for row in SEED:
            book, created = Book.objects.get_or_create(
                title=row["title"],
                defaults={
                    "author": row["author"],
                    "year": row["year"],
                    "misc": row["misc"],
                },
            )
            status = "created" if created else "exists"
            self.stdout.write(f"  [{status}] {book}")
        self.stdout.write(self.style.SUCCESS(f"total books: {Book.objects.count()}"))

    def _show(self):
        for b in Book.objects.all():
            self.stdout.write(
                json.dumps(
                    {"id": b.id, "title": b.title, "author": b.author, "year": b.year, "misc": b.misc},
                    indent=2,
                )
            )
