"""
Showcase the Location tree: print each root and its descendants with
indentation. Also count how many incidents live below each node — the
answer you get "for free" from MP_Node's descendant lookups.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from incidents.models import Incident, Location


class Command(BaseCommand):
    help = "Print the Location tree with incident counts per subtree."

    def handle(self, *args, **options):
        roots = Location.get_root_nodes()
        if not roots.exists():
            self.stdout.write("no locations yet — run `seed_raw` and `process` first.")
            return

        for root in roots:
            self._print_subtree(root, depth=0)

    def _print_subtree(self, node: Location, depth: int) -> None:
        indent = "  " * depth
        # All incidents attached to this node *or any descendant*.
        descendant_ids = list(node.get_descendants().values_list("id", flat=True))
        count = Incident.objects.filter(
            location_id__in=[node.id, *descendant_ids]
        ).count()
        self.stdout.write(
            f"{indent}{node.name}  [{node.level}]  ({count} incident{'s' if count != 1 else ''})"
        )
        for child in node.get_children():
            self._print_subtree(child, depth + 1)
