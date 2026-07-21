import json
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from landingpages.models import LandingPage
from leads.models import Lead
from tenants.models import Tenant

from .models import TelegramIntegration, TelegramLinkCode
from .services import notify_new_lead, send_telegram_message

WEBHOOK_SECRET = "test-webhook-secret"


def webhook_url(secret=WEBHOOK_SECRET):
    return reverse("telegram_webhook:webhook", kwargs={"secret": secret})


def telegram_update(chat_id, text):
    return {"message": {"chat": {"id": chat_id}, "text": text}}


@override_settings(TELEGRAM_WEBHOOK_SECRET=WEBHOOK_SECRET, TELEGRAM_BOT_TOKEN="test-token")
class TelegramWebhookTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Diamond Towers", slug="diamond-towers")
        self.link_code = TelegramLinkCode.generate_for(self.tenant)

    @patch("telegram_integration.services.requests.post")
    def test_valid_start_code_activates_integration(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None

        response = self.client.post(
            webhook_url(),
            data=json.dumps(telegram_update(12345, f"/start {self.link_code.code}")),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        integration = TelegramIntegration.objects.get(tenant=self.tenant)
        self.assertTrue(integration.is_active)
        self.assertEqual(integration.chat_id, "12345")
        self.link_code.refresh_from_db()
        self.assertTrue(self.link_code.used)

    @patch("telegram_integration.services.requests.post")
    def test_expired_code_does_not_activate_integration(self, mock_post):
        self.link_code.expires_at = timezone.now() - timedelta(minutes=1)
        self.link_code.save()

        self.client.post(
            webhook_url(),
            data=json.dumps(telegram_update(999, f"/start {self.link_code.code}")),
            content_type="application/json",
        )

        self.assertFalse(TelegramIntegration.objects.filter(tenant=self.tenant).exists())

    @patch("telegram_integration.services.requests.post")
    def test_unknown_code_does_not_activate_integration(self, mock_post):
        self.client.post(
            webhook_url(),
            data=json.dumps(telegram_update(999, "/start codigo-invalido")),
            content_type="application/json",
        )
        self.assertFalse(TelegramIntegration.objects.filter(tenant=self.tenant).exists())

    def test_wrong_secret_is_rejected(self):
        response = self.client.post(
            webhook_url(secret="wrong-secret"),
            data=json.dumps(telegram_update(1, "/start x")),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


@override_settings(TELEGRAM_BOT_TOKEN="test-token", SITE_URL="http://testserver")
class LeadNotificationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Diamond Towers", slug="diamond-towers")
        self.page = LandingPage.objects.create(
            tenant=self.tenant, title="Casas em Tramandaí", status=LandingPage.PUBLISHED
        )
        TelegramIntegration.objects.create(
            tenant=self.tenant, chat_id="555", is_active=True, linked_at=timezone.now()
        )

    @patch("telegram_integration.services.requests.post")
    def test_new_lead_triggers_telegram_notification(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None

        Lead.objects.create(
            tenant=self.tenant,
            landing_page=self.page,
            name="Maria",
            email="maria@example.com",
            phone="51999999999",
            city="Torres",
        )

        self.assertTrue(mock_post.called)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"]["chat_id"], "555")
        self.assertIn("Maria", kwargs["data"]["text"])
        self.assertIn("Casas em Tramandaí", kwargs["data"]["text"])

    @patch("telegram_integration.services.requests.post", side_effect=requests.Timeout)
    def test_telegram_timeout_does_not_raise_or_block_lead_creation(self, mock_post):
        # This is the concrete proof of PRD §7.7's "silent failure never
        # blocks the visitor" requirement: the Lead must exist even though
        # the Telegram call raised.
        lead = Lead.objects.create(
            tenant=self.tenant,
            landing_page=self.page,
            name="Maria",
            email="maria2@example.com",
            phone="51999999999",
            city="Torres",
        )
        self.assertIsNotNone(lead.pk)
        self.assertTrue(mock_post.called)

    def test_no_notification_sent_when_integration_inactive(self):
        TelegramIntegration.objects.filter(tenant=self.tenant).update(is_active=False)
        with patch("telegram_integration.services.requests.post") as mock_post:
            Lead.objects.create(
                tenant=self.tenant,
                landing_page=self.page,
                name="Sem Integração",
                email="sem@example.com",
                phone="1",
                city="Torres",
            )
            mock_post.assert_not_called()

    @patch("telegram_integration.services.requests.post")
    def test_send_telegram_message_returns_false_without_bot_token(self, mock_post):
        with override_settings(TELEGRAM_BOT_TOKEN=""):
            result = send_telegram_message("555", "hello")
        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch("telegram_integration.services.requests.post")
    def test_notify_new_lead_returns_false_when_no_active_integration(self, mock_post):
        TelegramIntegration.objects.filter(tenant=self.tenant).delete()
        page = LandingPage.objects.create(tenant=self.tenant, title="Outra página")
        lead = Lead(
            tenant=self.tenant,
            landing_page=page,
            name="X",
            email="x@example.com",
            phone="1",
            city="Torres",
        )
        result = notify_new_lead(lead)
        self.assertFalse(result)
        mock_post.assert_not_called()
