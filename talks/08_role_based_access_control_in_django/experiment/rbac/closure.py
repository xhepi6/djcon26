"""Transitive-closure rebuild for Role hierarchy.

Rebuilds the whole `RoleAncestry` table from scratch. O(N*depth) where N is the
number of roles. Fine for the demo; for a large real system you'd do:

- An incremental rebuild (only affected subtrees), or
- Delegate the whole thing to Postgres via a MATERIALIZED VIEW + pgtrigger
  (authentik's production approach).

The semantics of the closure are what matter here — not the refresh strategy.
"""

from django.db import transaction

from .models import Role, RoleAncestry


def rebuild_role_ancestry() -> None:
    """Drop and rebuild RoleAncestry. Always leaves self-links at depth 0."""
    with transaction.atomic():
        RoleAncestry.objects.all().delete()

        roles = list(Role.objects.all())
        if not roles:
            return

        by_id: dict[int, Role] = {r.pk: r for r in roles}
        rows: list[RoleAncestry] = [
            RoleAncestry(ancestor=r, descendant=r, depth=0) for r in roles
        ]

        for r in roles:
            cur = r
            depth = 0
            seen: set[int] = {r.pk}  # defensive against accidental cycles
            while cur.parent_id and cur.parent_id not in seen:
                depth += 1
                rows.append(
                    RoleAncestry(
                        ancestor_id=cur.parent_id,
                        descendant=r,
                        depth=depth,
                    )
                )
                seen.add(cur.parent_id)
                cur = by_id[cur.parent_id]

        RoleAncestry.objects.bulk_create(rows)
