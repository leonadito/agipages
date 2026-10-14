from django.db.models.signals import post_save
from django.dispatch import receiver

from leads.models import Lead

from .services import send_lead_conversion_event


@receiver(post_save, sender=Lead)
def send_lead_conversion_event_on_creation(sender, instance, created, raw=False, **kwargs):
    # raw = loaddata (copying data between databases): the lead already
    # existed, so nothing must be sent again.
    if created and not raw:
        send_lead_conversion_event(instance)
