from django.apps import AppConfig


class MetaConversionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "meta_conversions"

    def ready(self):
        from . import signals  # noqa: F401
