from django.core.management.base import BaseCommand

from tenants.traefik import regenerate_traefik_config


class Command(BaseCommand):
    help = (
        "Regenera traefik/dynamic/tenants.yml a partir dos tenants com "
        "domínio verificado. Roda automaticamente via signal a cada "
        "alteração de Tenant — este comando serve para forçar a "
        "regeneração manualmente (ex: logo após o deploy)."
    )

    def handle(self, *args, **options):
        path = regenerate_traefik_config()
        self.stdout.write(self.style.SUCCESS(f"Configuração gerada em {path}"))
