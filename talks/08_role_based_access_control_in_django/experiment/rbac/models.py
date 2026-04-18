"""RBAC data model.

Three tables is the whole thing:

    Role          — named bundle of permissions, optional parent (→ hierarchy)
    RoleAncestry  — transitive-closure CACHE over Role.parent. One row per
                    (ancestor, descendant, depth) pair, INCLUDING self-links at
                    depth 0. This is what turns the recursive hierarchy walk
                    into a single JOIN.
    UserRole      — assignment. A user holds a role, optionally scoped to a
                    specific object (GenericForeignKey), optionally with an
                    expiry (just-in-time access).

Permissions reuse Django's `auth.Permission` — including the custom ones
declared via `Meta.permissions`. Nothing special needed.
"""

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Role(models.Model):
    """A named bundle of permissions, optionally parented to another Role."""

    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
    )

    def __str__(self) -> str:
        return self.name


class RoleAncestry(models.Model):
    """Transitive closure cache over Role.parent.

    One row per (ancestor, descendant, depth). For every role R we store
    (R, R, 0) — the self-link — so the single JOIN `descendant=R` also covers
    "R itself".

    Maintained by post_save / post_delete signals on `Role` (see signals.py).
    In production with PostgreSQL you'd implement this as a MATERIALIZED VIEW
    + `django-pgtrigger` so the refresh runs inside the DB — authentik does
    exactly that with `authentik_core_groupancestry`.
    """

    ancestor = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="descendant_links"
    )
    descendant = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="ancestor_links"
    )
    depth = models.PositiveIntegerField()

    class Meta:
        unique_together = [("ancestor", "descendant")]
        indexes = [
            models.Index(fields=["descendant", "ancestor"]),
        ]

    def __str__(self) -> str:
        return f"{self.ancestor} → {self.descendant} (d={self.depth})"


class UserRole(models.Model):
    """The assignment table.

    - If `content_type` / `object_id` are NULL the role is GLOBAL.
    - Otherwise the role applies only when the permission check targets that
      specific object (object-level perms, a la Guardian).
    - `expires_at` is the just-in-time lever: a UserRole past its expiry is
      excluded by the has_perm query.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rbac_roles",
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    scope = GenericForeignKey("content_type", "object_id")

    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "content_type", "object_id"]),
        ]

    def __str__(self) -> str:
        where = "globally" if self.content_type_id is None else f"on {self.scope}"
        when = "" if self.expires_at is None else f" (expires {self.expires_at.isoformat()})"
        return f"{self.user} as {self.role} {where}{when}"
