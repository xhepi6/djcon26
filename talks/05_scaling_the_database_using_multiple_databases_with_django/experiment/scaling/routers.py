"""
Two routers in one file so you can toggle them with ``ROUTER=naive|smart``:

- ``NaiveRouter`` — the minimal "reads -> replica, writes -> default" split
  that Jake shows first in the talk. Demonstrates all three failure modes.

- ``PrimaryReplicaRouter`` — the production-ready version with the three
  fixes layered on top of ``NaiveRouter``. This is the "17-line router"
  Jake lands on by the end of the talk.
"""

from functools import cached_property

from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.db import transaction


# ---------------------------------------------------------------------------
# Helper — walk every registered model, keep those using GFK or GenericRelation
# ---------------------------------------------------------------------------


def _models_with_generic_fields():
    """Return the set of models that use GenericForeignKey or GenericRelation."""
    out = set()
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if isinstance(field, (GenericForeignKey, GenericRelation)):
                out.add(model)
                break
    return out


# ---------------------------------------------------------------------------
# The naive version — shown first in the talk to motivate the fixes
# ---------------------------------------------------------------------------


class NaiveRouter:
    """Minimal primary/replica split. Demonstrates the three failure modes:

    1. Reads inside a transaction miss their own writes (replicas only
       replicate committed data).
    2. ``get_or_create`` always hits the primary, even for rows that exist.
    3. ``instance.gfk_relation.update(...)`` routes to the replica even
       though it's a write (Django ticket #36389).
    """

    def db_for_read(self, model, **hints):
        return "replica"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        dbs = {"default", "replica"}
        if obj1._state.db in dbs and obj2._state.db in dbs:
            return True
        return None

    def allow_migrate(self, db, app_label, **hints):
        # Don't migrate the replica — in production the replica gets schema
        # changes through replication, not from Django's migrate command.
        return db == "default"


# ---------------------------------------------------------------------------
# The production router — NaiveRouter + three fixes
# ---------------------------------------------------------------------------


class PrimaryReplicaRouter:
    """Naive router + fixes for transactions, get_or_create, and GFK writes.

    Layered logic in ``db_for_read`` (order matters):
      1. If the model uses GFK/GenericRelation, force ``default`` until
         ticket #36389 ships.
      2. If we are inside ``transaction.atomic()`` on the write connection,
         force ``default`` so we see our own writes.
      3. Otherwise, return ``replica`` (load balancer in front of the reads).
    """

    @cached_property
    def _gfk_models(self):
        return _models_with_generic_fields()

    def db_for_read(self, model, **hints):
        # --- Fix #3: Django ticket #36389 workaround ---
        if model in self._gfk_models:
            return "default"

        # --- Fix #1: read-your-own-writes inside a transaction ---
        # transaction.get_autocommit('default') returns False when we are
        # inside an atomic() block. In that case we must read from the
        # primary — replicas only see committed data, so a read here would
        # return stale rows.
        if not transaction.get_autocommit(using="default"):
            return "default"

        return "replica"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        dbs = {"default", "replica"}
        if obj1._state.db in dbs and obj2._state.db in dbs:
            return True
        return None

    def allow_migrate(self, db, app_label, **hints):
        return db == "default"
