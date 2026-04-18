from django.db import models


class Book(models.Model):
    """The resource we will protect with RBAC.

    Meta.permissions declares two CUSTOM (non-CRUD) permissions — the talk
    stressed that bolting custom permissions onto Django alone gets painful.
    With our own backend they're just `auth.Permission` rows like any other.
    """

    title = models.CharField(max_length=200, unique=True)

    class Meta:
        permissions = [
            ("copy_book", "Can copy a book"),
            ("archive_book", "Can archive a book"),
        ]

    def __str__(self) -> str:
        return self.title
