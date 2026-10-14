"""Delivery of each form lead to the CRM (metaleads), Phase 4.

After a Lead is saved, a task (django.tasks, database backend, run by the
container's db_worker) POSTs it to metaleads' /api/v1/leads with the service
token, naming the tenant by its core uuid. Retries with growing waits until
metaleads confirms; the Idempotency-Key is the lead's uuid, so a retry never
creates a second lead there. The lead stays in agipages too (until Phase 8).

Off unless METALEADS_API_URL and METALEADS_API_TOKEN are set (production
keeps working as before until the cutover).
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.tasks import task
from django.utils import timezone

from .models import Lead

logger = logging.getLogger(__name__)

RETRY_WAITS = [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2),
               timedelta(hours=6), timedelta(hours=12), timedelta(hours=24)]
MAX_ATTEMPTS = len(RETRY_WAITS) + 1


def enabled():
    return bool(getattr(settings, "METALEADS_API_URL", "") and getattr(settings, "METALEADS_API_TOKEN", ""))


def page_url(page):
    tenant = page.tenant
    path = f"{page.slug}/" if page.slug else ""
    if tenant.custom_domain and tenant.domain_verified:
        return f"https://{tenant.custom_domain}/{path}"
    return f"{settings.SITE_URL.rstrip('/')}/{tenant.slug}/{path}"


def _platform(lead):
    source = (lead.utm_source or "").lower()
    if lead.fbclid or any(s in source for s in ("facebook", "instagram", "meta", "fb", "ig")):
        return "meta"
    if lead.gclid or "google" in source:
        return "google"
    if any([lead.utm_source, lead.utm_medium, lead.utm_campaign]):
        return "other"
    return "direct"


def build_payload(lead):
    page = lead.landing_page
    labels = {f.field_key: f.label for f in page.form_fields.all()}
    return {
        "tenant": str(lead.tenant.core_uuid),
        "source": "agipages_form",
        "external_id": str(lead.uuid),
        # Real date of the lead: leads sent late (retries, batches) keep it.
        "occurred_at": lead.created_at.isoformat(),
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "city": lead.city,
        "form_answers": lead.extra_field_values or {},
        "landing_page": {"id": str(page.uuid), "name": page.title, "url": page_url(page)},
        "attribution": {
            "platform": _platform(lead),
            "kind": "landing_page",
            "utm_source": lead.utm_source,
            "utm_medium": lead.utm_medium,
            "utm_campaign": lead.utm_campaign,
            "utm_term": lead.utm_term,
            "utm_content": lead.utm_content,
            "gclid": lead.gclid,
            "fbclid": lead.fbclid,
            "raw": {
                "agipages_lead": str(lead.uuid),
                "form_labels": labels,
                "fbp": lead.fbp,
                "fbc": lead.fbc,
                "created_at": lead.created_at.isoformat(),
            },
        },
    }


@task
def send_lead_to_metaleads(lead_id):
    lead = Lead.objects.select_related("tenant", "landing_page", "landing_page__tenant").filter(pk=lead_id).first()
    if lead is None or lead.metaleads_sent_at:
        return "nada a enviar"
    lead.metaleads_attempts += 1
    try:
        if not lead.tenant.core_uuid:
            raise ValueError("tenant ainda sem ligação com o core (core_uuid)")
        response = requests.post(
            f"{settings.METALEADS_API_URL.rstrip('/')}/api/v1/leads",
            json=build_payload(lead),
            headers={
                "Authorization": f"Bearer {settings.METALEADS_API_TOKEN}",
                "Idempotency-Key": f"agipages-lead-{lead.uuid}",
            },
            timeout=15,
        )
        if response.status_code not in (200, 201):
            raise ValueError(f"HTTP {response.status_code}: {response.text[:300]}")
        lead.metaleads_lead_uuid = response.json()["lead"]
        lead.metaleads_sent_at = timezone.now()
        lead.metaleads_error = ""
        lead.save(update_fields=["metaleads_lead_uuid", "metaleads_sent_at", "metaleads_error", "metaleads_attempts"])
        return str(lead.metaleads_lead_uuid)
    except (requests.RequestException, ValueError, KeyError) as exc:
        lead.metaleads_error = str(exc)[:1000]
        lead.save(update_fields=["metaleads_error", "metaleads_attempts"])
        if lead.metaleads_attempts < MAX_ATTEMPTS:
            wait = RETRY_WAITS[lead.metaleads_attempts - 1]
            send_lead_to_metaleads.using(run_after=timezone.now() + wait).enqueue(lead_id)
        else:
            logger.error("Lead %s não chegou ao metaleads depois de %s tentativas: %s", lead.uuid, lead.metaleads_attempts, exc)
        return f"falhou: {exc}"


@receiver(post_save, sender=Lead)
def queue_lead_for_metaleads(sender, instance, created, raw=False, **kwargs):
    # raw = loaddata (copying data between databases): already delivered.
    if created and not raw and enabled():
        transaction.on_commit(lambda: send_lead_to_metaleads.enqueue(instance.pk))
