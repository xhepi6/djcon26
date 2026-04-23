# Scaling the Database Using Multiple Databases with Django

> **Speaker:** Jake Howard — Torchbox (Wagtail core team), filed the Django tickets referenced in this talk
> **Event:** DjangoCon Europe 2026 (Greece)

## What is this about?

When one web server isn't enough you scale horizontally — you spin up more workers. When one database isn't enough it's much harder: you can only throw so much hardware at a single box. A pragmatic next step is **one primary for writes, one or more read replicas for reads**. Django has multi-DB support out of the box, but leaves "which query goes where" up to you. This talk walks through a 17-line `DATABASE_ROUTERS` implementation that gets you 90% of the way there, plus the three real-world gotchas Jake hit in production.

## The Problem

- A single database becomes the scaling bottleneck of most Django apps
- Vertical scaling has a ceiling (and a price)
- Reliability needs (failover, HA) also push you toward multiple database servers
- Django ships multi-DB primitives but no opinion about **how** to split traffic
- `Model.objects.using('replica')` everywhere is noisy, easy to forget, and impossible to retrofit

## The Solution

A **database router** — a small class with four methods that Django calls for every query:

| Method | When Django calls it | What you return |
|---|---|---|
| `db_for_read(model, **hints)` | Before every read (`.get/.filter/.count/...`) | Alias to use, or `None` |
| `db_for_write(model, **hints)` | Before every write (`.save/.create/.update/...`) | Alias to use, or `None` |
| `allow_relation(obj1, obj2, **hints)` | When building a FK between two instances | `True` / `False` / `None` |
| `allow_migrate(db, app_label, **hints)` | During `migrate` | `True` / `False` / `None` |

Returning `None` = "no opinion, try the next router"; the `DATABASE_ROUTERS` list is consulted in order.

Put a load balancer (HAProxy / RDS Proxy / pgBouncer) in front of your replicas and Django only needs **two** aliases: `default` (primary) and `replica` (the LB endpoint). Your app code stays the same — the router does the routing.

Then handle the three gotchas:

1. **Transactions** — reads inside `atomic()` see zero rows for their own writes (replicas only see committed data). Fix: check `transaction.get_autocommit()` in `db_for_read` and fall back to primary inside transactions.
2. **`get_or_create`** — always goes to primary, even for rows that already exist. Fix: a `replica_aware_get_or_create` helper that tries `.get()` first.
3. **Generic foreign keys** — Django bug [#36389](https://code.djangoproject.com/ticket/36389): `instance.relation.update(...)` on a `GenericRelation` routes to the read connection even though it's a write. Fix: walk `apps.get_models()` at import time, find models with `GenericForeignKey` / `GenericRelation`, and force them to `default`.

## How to Use It

### Install

Nothing extra — it's all in Django:

```bash
pip install "Django>=5.2"
```

Django 5.2 is significant: ticket [#35967](https://code.djangoproject.com/ticket/35967) (also Jake's) fixed `serialized_rollback` breaking with `TEST.MIRROR`. On 5.2+ you don't have to hand-patch tests.

### 1. Settings

```python
# config/settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp",
        "HOST": "primary.db.internal",
        # ...
    },
    "replica": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myapp",
        "HOST": "replica-lb.db.internal",   # load balancer in front of the replicas
        # Tests share the default DB — MIRROR avoids creating a second test DB
        "TEST": {"MIRROR": "default"},
    },
}

DATABASE_ROUTERS = ["myapp.routers.PrimaryReplicaRouter"]
```

### 2. The router (the 17 lines)

```python
# myapp/routers.py
from functools import cached_property

from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.db import transaction


def _models_with_generic_fields():
    """Walk every registered model, keep those with GFK or GenericRelation."""
    out = set()
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if isinstance(field, (GenericForeignKey, GenericRelation)):
                out.add(model)
                break
    return out


class PrimaryReplicaRouter:
    @cached_property
    def _gfk_models(self):
        return _models_with_generic_fields()

    def db_for_read(self, model, **hints):
        # Fix #3: GenericRelation writes wrongly use the read connection
        # (Django ticket #36389). Force GFK models to the write connection.
        if model in self._gfk_models:
            return "default"
        # Fix #1: replicas only see committed data. Inside a transaction
        # we must read from the primary to see our own writes.
        if not transaction.get_autocommit(using="default"):
            return "default"
        return "replica"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        # Both aliases carry the same data — cross-alias FKs are fine.
        dbs = {"default", "replica"}
        if obj1._state.db in dbs and obj2._state.db in dbs:
            return True
        return None

    def allow_migrate(self, db, app_label, **hints):
        # Only the primary is migrated; replicas are populated via replication.
        return db == "default"
```

### 3. Fix #2 — replica-aware `get_or_create`

```python
# myapp/helpers.py
def replica_aware_get_or_create(manager, defaults=None, **kwargs):
    """Try .get() on the replica first; only hit primary on miss.

    Plain Model.objects.get_or_create() always goes to the write connection
    (Django guarantees read-your-writes). When the row usually exists, that
    means every call hits the primary — ignoring the whole point of a replica.
    """
    try:
        return manager.get(**kwargs), False
    except manager.model.DoesNotExist:
        # Unhappy path — extra query, but rare in practice.
        return manager.get_or_create(defaults=defaults or {}, **kwargs)
```

Use it like:

```python
author, created = replica_aware_get_or_create(
    Author.objects, defaults={"bio": ""}, name="Jake",
)
```

### 4. Testing multi-DB

```python
from django.test import TransactionTestCase

class RoutingTests(TransactionTestCase):
    databases = {"default", "replica"}    # or "__all__"

    def test_write_then_read_uses_primary_inside_atomic(self):
        from django.db import transaction
        Author.objects.create(name="A")
        with transaction.atomic():
            Author.objects.create(name="B")
            # Without the autocommit check this would be 0 on a real replica.
            self.assertEqual(Author.objects.count(), 2)
```

Requires `TransactionTestCase` (not `TestCase`) when using `TEST.MIRROR` — the mirror depends on transactions being per-test, not per-class.

## Experiment

This folder is a runnable Django project that demonstrates all three challenges with a **fake replication** model: two SQLite files, `primary.sqlite3` and `replica.sqlite3`, and a `sync_replica` command that copies one into the other. This lets you *see* the replication lag in a single process.

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data       # populates primary, syncs to replica
python manage.py runserver
```

Routes:

| Route | Description |
|---|---|
| `/` | Home page with available commands |
| `/test/` | Interactive test panel -- run all demos from the browser |

Management commands:

```bash
python manage.py demo_lag            # write to primary, read from replica before sync
python manage.py demo_atomic         # transaction + read-your-own-writes
python manage.py demo_get_or_create  # standard vs replica-aware get_or_create
python manage.py demo_gfk_bug       # reproduces Django #36389 and the workaround
python manage.py sync_replica        # copy primary -> replica to simulate replication
python manage.py test scaling        # runs the bug reproduction as a TransactionTestCase
```

You can also toggle the router mode via an env var to see the failure modes:

```bash
ROUTER=naive  python manage.py demo_atomic          # shows the bug
ROUTER=smart  python manage.py demo_atomic          # shows the fix (default)
ROUTER=naive  python manage.py demo_gfk_bug
```

What each command shows:

| Command | Demonstrates |
|---|---|
| `demo_lag` | Replicas don't see un-replicated data. Sync fixes it |
| `demo_atomic` | Inside `atomic()`, naive router returns 0; smart router reads from primary |
| `demo_get_or_create` | `get_or_create` always hits primary; `replica_aware_get_or_create` uses replica on the happy path |
| `demo_gfk_bug` | `instance.relation.update(text=...)` lands on the replica with the naive router; smart router forces it to primary |

Key files:
- `scaling/routers.py` — both `NaiveRouter` and the full `PrimaryReplicaRouter`
- `scaling/helpers.py` — `replica_aware_get_or_create`
- `scaling/models.py` — two tiny apps, one with a `GenericForeignKey` for the bug demo
- `scaling/management/commands/sync_replica.py` — copies primary -> replica to simulate replication
- `scaling/tests.py` — the GFK write-routing bug reproduced as a `TransactionTestCase`
- `test_views.py` — test panel API endpoints (separated from app code)
- `templates/test.html` — interactive test panel UI

## Key Takeaways

- **A router is a ~20-line class with four methods.** You don't need a library, an extension, or any third-party dependency
- **`transaction.get_autocommit('default')`** is the canonical way to detect "am I inside `atomic()`?" from inside a router — use it to route reads to primary mid-transaction
- **`get_or_create` + replicas is a performance footgun.** Use a two-step helper for the common-path optimization
- **Put a load balancer in front of your replicas** so Django only needs one `replica` alias; scaling the replica tier becomes an infra-only change
- **`TEST.MIRROR`** points a test DB alias at another so your tests don't need two separate test databases. Django 5.2 finally made this work with `serialized_rollback`
- **Generic foreign keys and routers don't get along** yet (ticket #36389). The pragmatic workaround is to detect GFK-using models and pin them to the write connection
- **`allow_migrate` should return `False` for replicas** — you don't migrate replicas, they get schema changes through replication

## Q&A Highlights

- **Can you still read stale data outside transactions?** Yes — replication lag is real. On AWS RDS it's usually single-digit ms, but there's no lower bound. If you need read-your-own-writes guarantees outside a transaction, either wrap the code in `atomic()` or explicitly use `Model.objects.using("default")`
- **Synchronous replication?** Some engines (Postgres via `synchronous_commit`, MySQL group replication) support it but at a latency cost. Useful for correctness-critical paths, overkill for general reads
- **How do you test this?** Unit tests with the router configured + `TransactionTestCase(databases="__all__")` cover most cases. For real infrastructure behavior, "test in production" (careful canary) is honestly the best Jake found
- **Alternative: per-view / per-request pinning?** Yes — middleware that sets a thread-local flag and a router that reads it. Works, but once your "always use primary" views grow, the replica advantage erodes. Doing it in the router (query-level) has a better blast radius

## Links

- Django multi-DB docs: <https://docs.djangoproject.com/en/5.2/topics/db/multi-db/>
- Django testing multi-DB: <https://docs.djangoproject.com/en/5.2/topics/testing/advanced/#testing-primaryreplica>
- Django ticket #36389 (GenericRelation + replica bug, open): <https://code.djangoproject.com/ticket/36389>
- Django ticket #35967 (`serialized_rollback` + MIRROR, fixed in 5.2): <https://code.djangoproject.com/ticket/35967>
- Jake's reproduction repo for #36389: <https://github.com/RealOrangeOne/django-generic-relation-db-repro>
- `transaction.get_autocommit`: <https://docs.djangoproject.com/en/5.2/topics/db/transactions/>
- Jake Howard at Torchbox: <https://www.djangoproject.com/weblog/2025/aug/03/dsf-member-of-the-month-jake-howard/>

---
*Summarized at DjangoCon Europe 2026*
