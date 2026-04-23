"""
ParseLocation — resolve ``raw_location_text`` to a ``Location`` tree node.

The input is a comma-separated string like ``"Carlsbad Caverns, NM, USA"``
or, for older reports, just ``"Arizona, USA"``. We walk right-to-left
(country → state → cave) so the tree grows from the root.

The same insight from the talk: the tree means it's fine that some
incidents attach at state level and others attach at cave level. A flat
(country/state/region/cave) column layout can't.
"""

from __future__ import annotations

from incidents.models import Incident, Location, LocationLevel
from incidents.operations.base import Operation, register


# Precedence from root to leaf — anything at position N is a child of the
# thing at position N-1.
LEVELS_FROM_ROOT = [
    LocationLevel.COUNTRY,
    LocationLevel.STATE,
    LocationLevel.REGION,
    LocationLevel.CAVE,
]


def _upsert_child(parent: Location | None, name: str, level: LocationLevel) -> Location:
    """Find-or-create a Location with this (name, level) under `parent`."""
    name = name.strip()
    if parent is None:
        existing = Location.get_root_nodes().filter(name=name, level=level).first()
        return existing or Location.add_root(name=name, level=level)
    existing = parent.get_children().filter(name=name, level=level).first()
    return existing or parent.add_child(name=name, level=level)


@register
class ParseLocation(Operation):
    label = "parse location"

    def should_run(self, incident: Incident) -> bool:
        return bool(incident.raw_location_text) and incident.location_id is None

    def run(self, incident: Incident) -> None:
        # Split "Carlsbad Caverns, NM, USA" → ["USA", "NM", "Carlsbad Caverns"]
        parts = [p.strip() for p in incident.raw_location_text.split(",") if p.strip()]
        if not parts:
            raise ValueError("empty location")
        parts = list(reversed(parts))

        if len(parts) > len(LEVELS_FROM_ROOT):
            raise ValueError(f"too many location levels: {parts!r}")

        parent: Location | None = None
        for name, level in zip(parts, LEVELS_FROM_ROOT):
            parent = _upsert_child(parent, name, level)

        assert parent is not None
        incident.location = parent
        incident.save(update_fields=["location"])
