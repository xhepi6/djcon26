"""Free-form has_perm() check, optionally printing the SQL Django generates."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from library.models import Book

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Run `user.has_perm(perm[, book])` and print True/False. With --sql "
        "the SQL statements executed during the check are printed too."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("perm", help="e.g. library.change_book")
        parser.add_argument(
            "--book",
            default=None,
            help="Optional Book.title for an object-scoped check.",
        )
        parser.add_argument(
            "--sql",
            action="store_true",
            help="Print the SQL executed during the has_perm call.",
        )

    def handle(self, *args, username, perm, book, sql, **options):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"no such user: {username}")

        obj = None
        if book:
            try:
                obj = Book.objects.get(title=book)
            except Book.DoesNotExist:
                raise CommandError(f"no such book: {book!r}")

        start = len(connection.queries_log) if sql else None
        if sql:
            from django.db import reset_queries
            reset_queries()
            connection.force_debug_cursor = True

        result = user.has_perm(perm, obj) if obj else user.has_perm(perm)

        target = "" if obj is None else f" on {obj.title}"
        style = self.style.SUCCESS if result else self.style.WARNING
        self.stdout.write(style(f"{username}.has_perm({perm!r}{target}) = {result}"))

        if sql:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("SQL:"))
            for q in connection.queries:
                self.stdout.write(f"  {q['sql']}")
