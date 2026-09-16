import logging

import requests

logger = logging.getLogger(__name__)

GOOGLE_FORMS_BASE = "https://docs.google.com/forms/d/e"


def send_lead_to_google_form(lead, timeout=5):
    """Mirrors a Lead into a tenant's pre-existing Google Forms, best-effort.

    The Lead is already committed to the database by the time this runs
    (see signals.py) — same silent-failure contract as
    telegram_integration.services.send_telegram_message and
    meta_conversions.services.send_lead_conversion_event: a Google Forms
    outage, timeout, or misconfiguration must never surface to the visitor
    who just submitted the public lead form.
    """
    landing_page = lead.landing_page
    if not landing_page.google_form_id:
        return False

    data = {}
    fixed_fields = [
        (landing_page.google_form_entry_name, lead.name),
        (landing_page.google_form_entry_phone, lead.phone),
        (landing_page.google_form_entry_email, lead.email),
        (landing_page.google_form_entry_city, lead.city),
    ]
    for entry_id, value in fixed_fields:
        if entry_id and value:
            data[entry_id] = value

    for form_field in landing_page.form_fields.all():
        if not form_field.google_form_entry_id:
            continue
        value = lead.extra_field_values.get(form_field.field_key)
        if value:
            data[form_field.google_form_entry_id] = value

    if not data:
        return False

    url = f"{GOOGLE_FORMS_BASE}/{landing_page.google_form_id}/formResponse"
    try:
        requests.post(url, data=data, timeout=timeout)
        return True
    except requests.RequestException:
        logger.exception(
            "Falha ao espelhar lead %s para o Google Forms %s",
            lead.pk,
            landing_page.google_form_id,
        )
        return False
