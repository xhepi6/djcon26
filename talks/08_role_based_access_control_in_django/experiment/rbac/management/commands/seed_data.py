"""Build the canonical scenario described in the README.

Roles (hierarchy, left root + one separate root):

    viewer            → view_book
      └─ editor       → change_book              (inherits view_book)
          └─ librarian → add_book, delete_book   (inherits the above)
    archiver          → archive_book             (custom, separate root)

Users (Django `auth.User` rows — authentication still works):

    alice     : editor       (global)
    bob       : viewer       (global)
                editor       (scoped to Book "Dune")
    carol     : librarian    (global, expires 10s after seed — just-in-time)
    dave      : archiver     (global, demonstrates custom perm)
    admin     : is_superuser = True (short-circuits every check)

Books: "Dune", "Hyperion", "Foundation".
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils import timezone

from library.models import Book
from rbac.models import Role, RoleAncestry, UserRole

User = get_user_model()


class Command(BaseCommand):
    help = "Seed users, roles (with hierarchy), books, and UserRole assignments."

    def handle(self, *args, **options):
        # Wipe anything we manage so re-running is idempotent.
        UserRole.objects.all().delete()
        RoleAncestry.objects.all().delete()
        Role.objects.all().delete()
        Book.objects.all().delete()
        User.objects.filter(username__in=["alice", "bob", "carol", "dave", "admin"]).delete()

        # --- Permissions ---------------------------------------------------
        ct = ContentType.objects.get_for_model(Book)
        perms = {p.codename: p for p in Permission.objects.filter(content_type=ct)}
        # Django autogenerates: add_book, change_book, delete_book, view_book
        # library.models.Book.Meta.permissions adds: copy_book, archive_book

        # --- Roles (with hierarchy) ----------------------------------------
        viewer = Role.objects.create(name="viewer")
        viewer.permissions.add(perms["view_book"])

        editor = Role.objects.create(name="editor", parent=viewer)
        editor.permissions.add(perms["change_book"])

        librarian = Role.objects.create(name="librarian", parent=editor)
        librarian.permissions.add(perms["add_book"], perms["delete_book"])

        archiver = Role.objects.create(name="archiver")  # separate root
        archiver.permissions.add(perms["archive_book"])  # custom perm

        # --- Books ---------------------------------------------------------
        dune, _     = Book.objects.get_or_create(title="Dune")
        hyperion, _ = Book.objects.get_or_create(title="Hyperion")
        Book.objects.get_or_create(title="Foundation")

        # --- Users & assignments ------------------------------------------
        alice = User.objects.create_user("alice", password="x")
        bob   = User.objects.create_user("bob",   password="x")
        carol = User.objects.create_user("carol", password="x")
        dave  = User.objects.create_user("dave",  password="x")
        User.objects.create_superuser("admin", email="admin@example.com", password="x")

        # alice: global editor → change_book + inherited view_book
        UserRole.objects.create(user=alice, role=editor)

        # bob: global viewer + editor scoped to Dune (object-level perms)
        UserRole.objects.create(user=bob, role=viewer)
        UserRole.objects.create(user=bob, role=editor, scope=dune)

        # carol: librarian with a 10-second expiry (just-in-time access)
        UserRole.objects.create(
            user=carol,
            role=librarian,
            expires_at=timezone.now() + timedelta(seconds=10),
        )

        # dave: archiver — demonstrates a custom, non-CRUD permission
        UserRole.objects.create(user=dave, role=archiver)

        self.stdout.write(self.style.SUCCESS(
            "Seeded: 4 roles (3-level hierarchy + 1 standalone), 3 books, "
            "5 users (1 superuser), 5 UserRole assignments. "
            "`python manage.py show_rbac` to inspect, `demo_checks` to see it in action."
        ))
