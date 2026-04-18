"""
Small demo models.

- ``Author`` / ``Book`` — plain relational pair for the transaction,
  get_or_create and replication-lag demos.

- ``Revision`` + ``MainModel`` — reproduce the GenericForeignKey routing
  bug (Django ticket #36389). Copied from Jake Howard's reproduction repo
  at https://github.com/RealOrangeOne/django-generic-relation-db-repro.
"""

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100, unique=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# GenericForeignKey pair — for the ticket #36389 demo
# ---------------------------------------------------------------------------


class Revision(models.Model):
    """A "target" model with a reverse GenericRelation."""

    note = models.CharField(max_length=100, blank=True)
    mains = GenericRelation("MainModel")

    def __str__(self):
        return f"Revision#{self.pk}"


class MainModel(models.Model):
    """A model pointing at any ``Revision`` via a GenericForeignKey."""

    text = models.CharField(max_length=100, blank=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="+",
    )
    object_id = models.CharField(max_length=255)
    revisions = GenericForeignKey("content_type", "object_id", for_concrete_model=False)
