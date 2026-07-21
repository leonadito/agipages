import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


def _bot_url(method):
    return f"{TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def send_telegram_message(chat_id, text, timeout=2):
    """Synchronous call with a short timeout, swallowing every failure.

    The Lead this notifies about is already committed to the database by
    the time this runs (see signals.py) — a Telegram outage, timeout, or
    misconfiguration must NEVER surface as an error to the visitor who
    just submitted the public lead form (PRD §7.7).
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN não configurado; notificação não enviada.")
        return False
    try:
        response = requests.post(
            _bot_url("sendMessage"),
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=timeout,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Falha ao enviar mensagem Telegram para chat_id=%s", chat_id)
        return False


def notify_new_lead(lead):
    from .models import TelegramIntegration

    try:
        integration = TelegramIntegration.objects.get(
            tenant_id=lead.tenant_id, is_active=True
        )
    except TelegramIntegration.DoesNotExist:
        return False

    lead_url = f"{settings.SITE_URL.rstrip('/')}/dashboard/leads/{lead.pk}/"
    text = (
        f"<b>Novo lead em {lead.landing_page.title}</b>\n"
        f"Nome: {lead.name}\n"
        f"Email: {lead.email}\n"
        f"Telefone: {lead.phone}\n"
        f"Cidade: {lead.city}\n\n"
        f"{lead_url}"
    )
    return send_telegram_message(integration.chat_id, text)
