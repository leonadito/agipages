from smtplib import SMTPException
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from landingpages.models import LandingPage, LandingPageFormField, validate_email_list
from leads.models import Lead
from tenants.models import Tenant


@override_settings(EMAIL_HOST="smtp.example.com", DEFAULT_FROM_EMAIL="noreply@agitare.com.br")
class LeadNotificationEmailTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Dr. Ibsen Diarlei", slug="dribsendiarlei")
        self.page = LandingPage.objects.create(
            tenant=self.tenant,
            title="Site",
            status=LandingPage.PUBLISHED,
            phone_label="Telefone / WhatsApp",
            lead_notification_emails="medico@example.com, clinica@example.com",
        )
        LandingPageFormField.objects.create(
            landing_page=self.page, field_key="assunto", label="Assunto"
        )

    def _create_lead(self, **kwargs):
        data = dict(
            tenant=self.tenant,
            landing_page=self.page,
            name="Maria",
            email="maria@example.com",
            phone="51999999999",
            city="Capão da Canoa",
            extra_field_values={"assunto": "Quero agendar uma consulta"},
        )
        data.update(kwargs)
        return Lead.objects.create(**data)

    def test_new_lead_emails_every_address_with_all_fields(self):
        self._create_lead()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["medico@example.com", "clinica@example.com"])
        # "." no nome exige aspas no cabeçalho (RFC 5322); formataddr cuida disso
        self.assertEqual(message.from_email, '"Dr. Ibsen Diarlei" <noreply@agitare.com.br>')
        self.assertEqual(message.reply_to, ["maria@example.com"])
        self.assertIn("Maria", message.subject)
        for expected in (
            "Nome: Maria",
            "E-mail: maria@example.com",
            "Telefone / WhatsApp: 51999999999",
            "Cidade: Capão da Canoa",
            "Assunto: Quero agendar uma consulta",
        ):
            self.assertIn(expected, message.body)

    def test_lead_without_email_has_no_reply_to(self):
        self._create_lead(email="")

        self.assertEqual(mail.outbox[0].reply_to, [])

    def test_page_without_addresses_sends_nothing(self):
        self.page.lead_notification_emails = ""
        self.page.save()

        self._create_lead()

        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_HOST="")
    def test_missing_smtp_config_sends_nothing(self):
        self._create_lead()

        self.assertEqual(mail.outbox, [])

    @patch("email_notifications.services.EmailMessage.send", side_effect=SMTPException)
    def test_smtp_failure_does_not_raise_or_block_lead_creation(self, mock_send):
        # Same silent-failure contract as telegram_integration/google_forms_integration:
        # the Lead must exist even though sending raised.
        lead = self._create_lead()

        self.assertTrue(mock_send.called)
        self.assertTrue(Lead.objects.filter(pk=lead.pk).exists())


class ValidateEmailListTests(TestCase):
    def test_accepts_blank_and_comma_separated_addresses(self):
        validate_email_list("")
        validate_email_list("a@example.com, b@example.com")

    def test_rejects_invalid_address(self):
        with self.assertRaises(ValidationError):
            validate_email_list("a@example.com, nao-e-email")
