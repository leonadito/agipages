from django.apps import AppConfig


class GoogleFormsIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "google_forms_integration"

    def ready(self):
        from . import signals  # noqa: F401
