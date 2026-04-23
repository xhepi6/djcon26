"""
Reliable Django Signals — the transactional outbox pattern.

Instead of executing receivers immediately, enqueue a task for each receiver
inside the sender's database transaction. The task is committed atomically
with the data change. A background worker picks it up after commit.
"""

import importlib
from collections.abc import Callable, Mapping
from typing import Any

from django.dispatch import Signal as DjangoSignal
from django.dispatch.dispatcher import NO_RECEIVERS
from django_tasks import task


# --- Qualified-name helpers ---------------------------------------------------
# We need to store a reference to each receiver as a string (it goes into the
# database queue). These two functions convert between callables and strings.


def callable_to_qualname(f: Callable[..., Any]) -> str:
    """Return '<module>::<qualname>' for a callable."""
    return f"{f.__module__}::{f.__qualname__}"


def qualname_to_callable(qualname: str) -> Callable[..., Any]:
    """Resolve '<module>::<qualname>' back to a callable."""
    module_name, func_qualname = qualname.split("::", 1)
    module = importlib.import_module(module_name)
    obj: Any = module
    for attr in func_qualname.split("."):
        obj = getattr(obj, attr)
    return obj


# --- Generic task that executes any receiver ----------------------------------


@task()
def execute_task_signal_receiver(
    *,
    receiver_qualname: str,
    named: Mapping[str, object],
) -> None:
    """Look up a receiver by its qualname and call it."""
    receiver = qualname_to_callable(receiver_qualname)
    receiver(signal=None, sender=None, **named)


# --- ReliableSignal -----------------------------------------------------------


class ReliableSignal(DjangoSignal):
    """A Signal subclass that enqueues receivers as database tasks.

    Use send_reliable() instead of send() or send_robust().
    Call it INSIDE transaction.atomic() so the task rows are committed
    atomically with your data change.
    """

    def send_reliable(self, sender: Any, **named: Any) -> None:
        if not self.receivers:
            return
        if self.sender_receivers_cache.get(sender) is NO_RECEIVERS:
            return

        sync_receivers, async_receivers = self._live_receivers(sender)
        assert not async_receivers, "Async receivers not supported by task backend"

        for receiver in sync_receivers:
            execute_task_signal_receiver.enqueue(
                receiver_qualname=callable_to_qualname(receiver),
                named=named,
            )
