from django.db.models.signals import post_save
from django.dispatch import receiver

from leads.models import Lead

from .services import send_lead_notification_email


@receiver(post_save, sender=Lead)
def email_lead_created(sender, instance, created, **kwargs):
    if created:
        send_lead_notification_email(instance)
