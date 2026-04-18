"""Keep the RoleAncestry cache fresh.

Every time a Role is saved or deleted, rebuild the closure. The Real Thing
(authentik) does this in-database with a pgtrigger + MV refresh — same
semantics, less app code on the hot path.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .closure import rebuild_role_ancestry
from .models import Role


@receiver(post_save, sender=Role)
@receiver(post_delete, sender=Role)
def _role_changed(sender, **kwargs) -> None:
    rebuild_role_ancestry()
