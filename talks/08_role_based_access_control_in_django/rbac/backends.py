"""Two auth backends, one purpose each.

The talk's whole thesis:
  * Django's authentication (user lookup, password check) is great — keep it.
  * Django's authorization (has_perm against auth_user_user_permissions +
    auth_group permissions) is the part that can't express group hierarchy,
    just-in-time access, object-level perms, etc. Replace it.

The way you "replace" it without touching Django core is:
  1. Subclass ModelBackend and make all the authz methods inert.
  2. Register your own backend after it in AUTHENTICATION_BACKENDS.

Django's backend chain takes the first backend that returns a non-None
value for has_perm. With ModelBackendNoAuthz returning False for every
check, the chain always proceeds to RBACBackend, which is the single source
of truth.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone

from .models import Role, UserRole


class ModelBackendNoAuthz(ModelBackend):
    """Django's ModelBackend with the authorization half removed.

    Direct analogue of authentik/core/auth.py:ModelBackendNoAuthz. Keeps
    `authenticate()` (inherited) so logging in / session handling still works.
    """

    def get_user_permissions(self, user_obj, obj=None):
        return set()

    def get_group_permissions(self, user_obj, obj=None):
        return set()

    def get_all_permissions(self, user_obj, obj=None):
        return set()

    def has_perm(self, user_obj, perm, obj=None):
        return False

    def has_module_perms(self, user_obj, app_label):
        return False

    def with_perm(self, perm, is_active=True, include_superusers=True, obj=None):
        return get_user_model().objects.none()


class RBACBackend:
    """Single-query authorization against Role / RoleAncestry / UserRole."""

    def authenticate(self, request, **credentials):
        # This backend answers authorization only.
        return None

    def get_user(self, user_id):
        return None

    # ---- the core question -------------------------------------------------

    def has_perm(self, user_obj, perm, obj=None) -> bool:
        if not user_obj or not user_obj.is_authenticated:
            return False
        if not user_obj.is_active:
            return False
        if user_obj.is_superuser:
            return True

        try:
            app_label, codename = perm.split(".", 1)
        except ValueError:
            return False

        direct_roles = self._direct_role_ids(user_obj, obj)

        # Any ancestor (including self at depth=0) of a directly-held role
        # holds this permission?
        #
        # Read the FK direction carefully:
        #   Role.descendant_links -> RoleAncestry rows where ancestor=this Role
        # So filtering Role.descendant_links__descendant__in=direct_roles reads:
        #   "Roles R such that some RoleAncestry(ancestor=R, descendant=D)
        #    exists with D in the user's directly-held roles"
        # i.e. the ancestors of anything the user holds (including self,
        # because we wrote depth-0 self-links into the closure).
        return Role.objects.filter(
            descendant_links__descendant__in=direct_roles,
            permissions__content_type__app_label=app_label,
            permissions__codename=codename,
        ).exists()

    def has_module_perms(self, user_obj, app_label: str) -> bool:
        if not user_obj or not user_obj.is_active:
            return False
        if user_obj.is_superuser:
            return True
        direct_roles = self._direct_role_ids(user_obj, obj=None)
        return Role.objects.filter(
            descendant_links__descendant__in=direct_roles,
            permissions__content_type__app_label=app_label,
        ).exists()

    def get_all_permissions(self, user_obj, obj=None) -> set[str]:
        """Return the set of 'app_label.codename' strings the user has."""
        from django.contrib.auth.models import Permission

        if not user_obj or not user_obj.is_active:
            return set()
        if user_obj.is_superuser:
            return {
                f"{p.content_type.app_label}.{p.codename}"
                for p in Permission.objects.select_related("content_type").all()
            }
        direct_roles = self._direct_role_ids(user_obj, obj)
        perms = Permission.objects.filter(
            roles__descendant_links__descendant__in=direct_roles,
        ).select_related("content_type").distinct()
        return {f"{p.content_type.app_label}.{p.codename}" for p in perms}

    # ---- helpers -----------------------------------------------------------

    def _direct_role_ids(self, user_obj, obj):
        """role_ids for `user_obj`, honoring object-scope and JIT expiry.

        Returns a QuerySet of role ids, suitable for use as a subquery.
        """
        qs = UserRole.objects.filter(user=user_obj).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        if obj is None:
            qs = qs.filter(content_type__isnull=True)
        else:
            ct = ContentType.objects.get_for_model(obj)
            qs = qs.filter(
                Q(content_type__isnull=True)
                | Q(content_type=ct, object_id=obj.pk)
            )
        return qs.values("role_id")
