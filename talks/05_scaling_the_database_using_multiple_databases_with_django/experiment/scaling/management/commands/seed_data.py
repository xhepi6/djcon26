"""Seed primary with a few authors + books, then sync the replica."""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from scaling.models import Author, Book


SEED = [
    ("Jake Howard", ["Wagtail Internals"]),
    ("Adrian Holovaty", ["The Django Book"]),
    ("Hanne Moa", ["Single-field Forms"]),
]


class Command(BaseCommand):
    help = "Populate the primary with demo data and sync to replica."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="wipe before seeding")

    def handle(self, *args, **options):
        if options["reset"]:
            Book.objects.all().delete()
            Author.objects.all().delete()

        for name, titles in SEED:
            # .using('default') is a belt-and-braces hint; writes already go
            # to default via the router's db_for_write().
            author, _ = Author.objects.using("default").get_or_create(name=name)
            for title in titles:
                Book.objects.using("default").get_or_create(title=title, author=author)

        self.stdout.write(
            self.style.SUCCESS(
                f"primary: {Author.objects.using('default').count()} authors, "
                f"{Book.objects.using('default').count()} books"
            )
        )
        call_command("sync_replica")
