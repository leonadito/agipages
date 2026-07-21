from django.db.models.signals import post_save
from django.dispatch import receiver

from leads.models import Lead

from .services import notify_new_lead


@receiver(post_save, sender=Lead)
def notify_lead_created(sender, instance, created, **kwargs):
    if created:
        notify_new_lead(instance)
