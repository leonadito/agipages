import logging
from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from landingpages.models import split_email_list

logger = logging.getLogger(__name__)


def send_lead_notification_email(lead):
    """E-mails a Lead to the addresses set on its landing page, best-effort.

    The Lead is already committed to the database by the time this runs
    (see signals.py) — same silent-failure contract as
    telegram_integration.services.send_telegram_message and
    google_forms_integration.services.send_lead_to_google_form: an SMTP
    outage, timeout, or misconfiguration must never surface to the visitor
    who just submitted the public lead form. EMAIL_TIMEOUT (settings) keeps
    a hung SMTP server from holding the request.
    """
    landing_page = lead.landing_page
    recipients = split_email_list(landing_page.lead_notification_emails)
    if not recipients:
        return False
    if not settings.EMAIL_HOST:
        logger.warning("EMAIL_HOST não configurado; aviso de lead por e-mail não enviado.")
        return False

    labels = {f.field_key: f.label for f in landing_page.form_fields.all()}
    lines = [
        f"Nome: {lead.name}",
        f"E-mail: {lead.email}",
        f"{landing_page.phone_label or 'Telefone'}: {lead.phone}",
        f"Cidade: {lead.city}",
    ]
    for key, value in (lead.extra_field_values or {}).items():
        lines.append(f"{labels.get(key, key)}: {value}")
    lead_url = f"{settings.SITE_URL.rstrip('/')}/dashboard/leads/{lead.pk}/"
    body = (
        f"Novo contato recebido pela página \"{landing_page.title}\".\n\n"
        + "\n".join(lines)
        + f"\n\nEnviado em: {timezone.localtime(lead.created_at):%d/%m/%Y %H:%M}\n"
        f"Ver no painel: {lead_url}\n"
    )

    # Remetente da plataforma, com o nome do tenant: o e-mail chega como
    # "Dr. Fulano <noreply@...>" e "responder" vai direto para o lead.
    from_email = formataddr((lead.tenant.name, parseaddr(settings.DEFAULT_FROM_EMAIL)[1]))
    message = EmailMessage(
        subject=f"Novo contato pelo site: {lead.name}",
        body=body,
        from_email=from_email,
        to=recipients,
        reply_to=[lead.email] if lead.email else None,
    )
    try:
        message.send()
        return True
    except Exception:
        logger.exception("Falha ao enviar aviso por e-mail do lead %s", lead.pk)
        return False
