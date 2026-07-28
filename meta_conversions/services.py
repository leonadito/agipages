import hashlib
import logging
import re

import requests

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hashed_email(email):
    email = (email or "").strip().lower()
    return _hash(email) if email else None


def _hashed_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None
    # Numbers stored without a country code are assumed Brazilian —
    # documented assumption, this platform has no other market today.
    if len(digits) in (10, 11):
        digits = f"55{digits}"
    return _hash(digits)


def _hashed_city(city):
    city = (city or "").strip().lower()
    return _hash(city) if city else None


def send_lead_conversion_event(lead):
    """Sends the "Lead" event to Meta's Conversions API, mirroring the
    fbq('track', 'Lead') browser-side Pixel call (see templates/public/
    partials/lead_form_success.html, same event_id — see event_id below)
    so ad delivery keeps working even when the browser pixel is lost
    (ad blockers, ITP, iOS 14+).

    Fails silently — same contract as
    telegram_integration.services.send_telegram_message: a Conversions API
    outage or missing configuration must never surface to the visitor who
    just submitted the public lead form. The Lead is already committed to
    the database by the time this runs (see signals.py).
    """
    pixel_id = lead.landing_page.facebook_pixel_id
    if not pixel_id:
        return False

    from .models import MetaConversionSettings

    try:
        conversion_settings = MetaConversionSettings.objects.get(tenant_id=lead.tenant_id)
    except MetaConversionSettings.DoesNotExist:
        return False
    if not conversion_settings.access_token:
        return False

    user_data = {}
    hashed_email = _hashed_email(lead.email)
    if hashed_email:
        user_data["em"] = [hashed_email]
    hashed_phone = _hashed_phone(lead.phone)
    if hashed_phone:
        user_data["ph"] = [hashed_phone]
    hashed_city = _hashed_city(lead.city)
    if hashed_city:
        user_data["ct"] = hashed_city
    if lead.ip_address:
        user_data["client_ip_address"] = lead.ip_address
    if lead.user_agent:
        user_data["client_user_agent"] = lead.user_agent
    if lead.fbp:
        user_data["fbp"] = lead.fbp
    if lead.fbc:
        user_data["fbc"] = lead.fbc

    event = {
        "event_name": "Lead",
        # Same value used by the browser Pixel's eventID (lead.pk) so Meta
        # deduplicates the two calls into a single conversion instead of
        # double-counting it.
        "event_id": str(lead.pk),
        "event_time": int(lead.created_at.timestamp()),
        "action_source": "website",
        "user_data": user_data,
    }
    payload = {
        "data": [event],
        "access_token": conversion_settings.access_token,
    }
    if conversion_settings.test_event_code:
        payload["test_event_code"] = conversion_settings.test_event_code

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{pixel_id}/events"
    try:
        response = requests.post(url, json=payload, timeout=3)
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception(
            "Falha ao enviar evento Lead para a Conversions API (pixel_id=%s, lead_id=%s)",
            pixel_id,
            lead.pk,
        )
        return False
