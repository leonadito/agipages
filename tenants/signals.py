from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Tenant
from .traefik import regenerate_traefik_config


@receiver(post_save, sender=Tenant)
@receiver(post_delete, sender=Tenant)
def regenerate_traefik_config_on_tenant_change(sender, **kwargs):
    regenerate_traefik_config()
