"""
Registry of pipeline operations.

Each submodule defines one subclass of ``Operation`` and applies the
``@register`` decorator. Importing the package is enough to populate the
registry — ``incidents.apps.IncidentsConfig.ready()`` does that at startup.

Execution order is the order in which they register. Dependencies between
operations are expressed via the ``requires`` attribute (a list of
``Operation`` subclasses), and enforced by the ``process`` management
command.
"""

from incidents.operations.base import Operation, get_registry, register

# Import the concrete operations so the decorators fire. The order here is
# the order the pipeline will execute them by default.
from incidents.operations import (  # noqa: F401,E402 — side-effectful imports
    parse_date,
    parse_location,
    fake_llm_rewrite,
    fake_llm_critic,
    classify_severity,
)

__all__ = ["Operation", "get_registry", "register"]
