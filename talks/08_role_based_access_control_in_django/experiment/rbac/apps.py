from django.apps import AppConfig


class RbacConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rbac"

    def ready(self) -> None:
        # Connect the post_save / post_delete signals that keep RoleAncestry fresh.
        from . import signals  # noqa: F401
