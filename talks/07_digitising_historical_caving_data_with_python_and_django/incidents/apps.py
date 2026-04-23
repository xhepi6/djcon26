from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "incidents"

    def ready(self):
        # Import the operation modules so their @register decorators run
        # and populate the registry at startup.
        from incidents import operations  # noqa: F401
