"""Run a table of canonical has_perm() calls — the one-slide tour of the design.

Covers:
  * hierarchy inheritance (alice inherits view_book via editor → viewer)
  * scoped assignment (bob can change_book only on Dune)
  * just-in-time expiry (carol — run soon after seed)
  * custom non-CRUD perm (dave's archive_book)
  * superuser short-circuit (admin wins everything)
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from library.models import Book

User = get_user_model()


CASES = [
    # (username, perm, book_title_or_None, expected, why)
    ("alice", "library.view_book",    None,        True,  "editor → viewer (closure)"),
    ("alice", "library.change_book",  None,        True,  "editor"),
    ("alice", "library.delete_book",  None,        False, "no librarian"),
    ("bob",   "library.view_book",    None,        True,  "viewer (global)"),
    ("bob",   "library.change_book",  None,        False, "no global editor"),
    ("bob",   "library.change_book",  "Dune",      True,  "editor scoped to Dune"),
    ("bob",   "library.change_book",  "Hyperion",  False, "scope mismatch"),
    ("carol", "library.add_book",     None,        True,  "librarian (if unexpired)"),
    ("carol", "library.delete_book",  None,        True,  "librarian (if unexpired)"),
    ("dave",  "library.archive_book", None,        True,  "archiver — custom perm"),
    ("dave",  "library.view_book",    None,        False, "archiver is a separate root"),
    ("admin", "library.archive_book", None,        True,  "is_superuser short-circuit"),
]


class Command(BaseCommand):
    help = "Run a battery of canonical has_perm() checks and print a results table."

    def handle(self, *args, **options):
        width_user, width_perm, width_obj, width_why = 7, 24, 12, 38

        header = (
            f"  {'user':<{width_user}} {'perm':<{width_perm}} "
            f"{'object':<{width_obj}} {'expected':<9} {'actual':<8} via"
        )
        self.stdout.write(header)
        self.stdout.write("  " + "-" * (len(header) + width_why))

        for username, perm, title, expected, why in CASES:
            user = User.objects.get(username=username)
            obj = Book.objects.get(title=title) if title else None
            actual = user.has_perm(perm, obj) if obj else user.has_perm(perm)

            tag = (
                self.style.SUCCESS("ok")
                if actual is expected
                else self.style.ERROR("MISMATCH")
            )
            self.stdout.write(
                f"  {username:<{width_user}} {perm:<{width_perm}} "
                f"{(title or '—'):<{width_obj}} {str(expected):<9} {str(actual):<8} "
                f"{why}  {tag}"
            )
