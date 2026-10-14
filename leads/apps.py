from django.apps import AppConfig


class LeadsConfig(AppConfig):
    name = 'leads'

    def ready(self):
        from . import metaleads  # noqa: F401  (queues each new lead for the CRM)
