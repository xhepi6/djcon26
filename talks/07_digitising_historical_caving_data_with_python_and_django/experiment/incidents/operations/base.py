"""
The pluggable-step base class and registry.

This is the core architectural pattern from the talk: a small contract
(``should_run`` / ``run``) every pipeline step implements, plus a registry
so the process command discovers all operations without an explicit
import-and-call list. New steps drop into ``incidents/operations/`` with a
single ``@register`` and become part of the pipeline.

The model side lives in ``models.OperationRun``: one row per
(incident, operation), storing status and error message. An operation can
depend on another by naming it in ``requires`` — the runner checks each
prereq has a ``SUCCESS`` row before running the dependent step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from incidents.models import Incident


_REGISTRY: list[type["Operation"]] = []


class Operation:
    """Base class for pipeline steps.

    Subclasses implement ``run``. Optionally override ``should_run`` to
    skip incidents the step doesn't apply to (e.g. a US-state normalizer
    should skip incidents outside the US).

    ``requires`` lists other operation classes that must have succeeded
    on the same incident before this one runs.
    """

    # Human-readable label; defaults to the class name.
    label: str | None = None

    # Operation classes whose SUCCESS is a precondition.
    requires: list[type["Operation"]] = []

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    def should_run(self, incident: "Incident") -> bool:
        """Return False to mark the incident as SKIPPED for this step."""
        return True

    def run(self, incident: "Incident") -> None:
        """Do the work. Raise to signal FAILED; return to signal SUCCESS."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def display(cls) -> str:
        return cls.label or cls.__name__


def register(op_cls: type[Operation]) -> type[Operation]:
    """Class decorator: add the operation to the pipeline registry."""
    if not issubclass(op_cls, Operation):
        raise TypeError(f"{op_cls} must subclass Operation")
    if op_cls in _REGISTRY:
        return op_cls
    _REGISTRY.append(op_cls)
    return op_cls


def get_registry() -> list[type[Operation]]:
    """Return the registered operations in execution order."""
    return list(_REGISTRY)
