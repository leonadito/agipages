from django.db.models.signals import post_save
from django.dispatch import receiver

from leads.models import Lead

from .services import send_lead_to_google_form


@receiver(post_save, sender=Lead)
def mirror_lead_to_google_form(sender, instance, created, **kwargs):
    if created:
        send_lead_to_google_form(instance)
