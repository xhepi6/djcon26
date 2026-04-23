"""
Fix #2 from the talk: a ``get_or_create`` variant that lets the replica
handle the happy path.

The built-in ``Model.objects.get_or_create()`` always routes through the
write connection, because Django wants to guarantee read-your-writes. For
a row that already exists, that means the primary answers *every* call —
which defeats the point of having replicas.

``replica_aware_get_or_create`` tries an optimistic ``.get()`` first (goes
to the replica via the router), and only falls back to the full
``get_or_create`` (which hits the primary) when the row is missing.

Caveats:
- On the unhappy path you pay one extra query.
- There is a small race window where a row exists on the primary but not
  yet on the replica; the fallback handles it naturally.
- For callers that need to react to the ``created`` flag with 100%
  accuracy, stick to ``get_or_create``.
"""


def replica_aware_get_or_create(manager, defaults=None, **kwargs):
    """
    Try ``manager.get(**kwargs)`` first (replica), fall back to
    ``manager.get_or_create(defaults=defaults, **kwargs)`` (primary).

    Returns ``(instance, created)`` just like ``get_or_create``.
    """
    try:
        return manager.get(**kwargs), False
    except manager.model.DoesNotExist:
        return manager.get_or_create(defaults=defaults or {}, **kwargs)
