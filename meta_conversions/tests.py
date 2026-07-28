import hashlib
from unittest.mock import patch

import requests
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from landingpages.models import LandingPage
from leads.models import Lead
from tenants.models import Tenant

from .models import MetaConversionSettings
from .services import send_lead_conversion_event


def _sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class LeadConversionEventTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Diamond Towers", slug="diamond-towers")
        self.page = LandingPage.objects.create(
            tenant=self.tenant,
            title="Casas em Tramandaí",
            status=LandingPage.PUBLISHED,
            facebook_pixel_id="123456789",
        )
        MetaConversionSettings.objects.create(
            tenant=self.tenant, access_token="test-token", test_event_code="TEST12345"
        )

    @patch("meta_conversions.services.requests.post")
    def test_new_lead_sends_hashed_event_matching_pixel_event_id(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None

        lead = Lead.objects.create(
            tenant=self.tenant,
            landing_page=self.page,
            name="Maria",
            email="Maria@Example.com",
            phone="(51) 99999-9999",
            city="Torres",
            fbp="fb.1.111.222",
            fbc="fb.1.111.333",
        )

        self.assertTrue(mock_post.called)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://graph.facebook.com/v21.0/123456789/events")
        payload = kwargs["json"]
        self.assertEqual(payload["access_token"], "test-token")
        self.assertEqual(payload["test_event_code"], "TEST12345")

        event = payload["data"][0]
        self.assertEqual(event["event_name"], "Lead")
        self.assertEqual(event["action_source"], "website")
        # Same ID the browser Pixel call uses (see
        # templates/public/partials/lead_form_success.html) so Meta
        # deduplicates instead of double-counting the conversion.
        self.assertEqual(event["event_id"], str(lead.pk))

        user_data = event["user_data"]
        self.assertEqual(user_data["em"], [_sha256("maria@example.com")])
        self.assertEqual(user_data["ph"], [_sha256("5551999999999")])
        self.assertEqual(user_data["ct"], _sha256("torres"))
        self.assertEqual(user_data["fbp"], "fb.1.111.222")
        self.assertEqual(user_data["fbc"], "fb.1.111.333")
        self.assertNotIn("Maria", str(user_data))

    @patch("meta_conversions.services.requests.post", side_effect=requests.Timeout)
    def test_timeout_does_not_raise_or_block_lead_creation(self, mock_post):
        lead = Lead.objects.create(
            tenant=self.tenant,
            landing_page=self.page,
            name="Maria",
            email="maria@example.com",
            phone="51999999999",
            city="Torres",
        )
        self.assertIsNotNone(lead.pk)
        self.assertTrue(mock_post.called)

    @patch("meta_conversions.services.requests.post")
    def test_no_call_when_landing_page_has_no_pixel_id(self, mock_post):
        page = LandingPage.objects.create(tenant=self.tenant, title="Sem pixel")
        lead = Lead(
            tenant=self.tenant,
            landing_page=page,
            name="X",
            email="x@example.com",
            phone="1",
            city="Torres",
        )
        result = send_lead_conversion_event(lead)
        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch("meta_conversions.services.requests.post")
    def test_no_call_when_no_settings_for_tenant(self, mock_post):
        other_tenant = Tenant.objects.create(name="Sem config", slug="sem-config")
        page = LandingPage.objects.create(
            tenant=other_tenant, title="Outra", facebook_pixel_id="999"
        )
        lead = Lead(
            tenant=other_tenant,
            landing_page=page,
            name="X",
            email="x@example.com",
            phone="1",
            city="Torres",
        )
        result = send_lead_conversion_event(lead)
        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch("meta_conversions.services.requests.post")
    def test_no_call_when_access_token_blank(self, mock_post):
        MetaConversionSettings.objects.filter(tenant=self.tenant).update(access_token="")
        lead = Lead(
            tenant=self.tenant,
            landing_page=self.page,
            name="X",
            email="x@example.com",
            phone="1",
            city="Torres",
        )
        result = send_lead_conversion_event(lead)
        self.assertFalse(result)
        mock_post.assert_not_called()


class MetaConversionSettingsViewTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a")
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b")
        self.user_a = User.objects.create_user(
            username="usuarioa", email="a@example.com", password="SenhaForte123", tenant=self.tenant_a
        )
        self.user_b = User.objects.create_user(
            username="usuariob", email="b@example.com", password="SenhaForte123", tenant=self.tenant_b
        )

    def test_saving_settings_only_affects_own_tenant(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse("meta_conversions:settings"),
            {"access_token": "token-a", "test_event_code": ""},
        )
        self.assertEqual(response.status_code, 302)

        settings_a = MetaConversionSettings.objects.get(tenant=self.tenant_a)
        self.assertEqual(settings_a.access_token, "token-a")
        self.assertFalse(MetaConversionSettings.objects.filter(tenant=self.tenant_b).exists())

    def test_cannot_view_or_edit_another_tenants_settings(self):
        MetaConversionSettings.objects.create(tenant=self.tenant_b, access_token="token-b")
        self.client.force_login(self.user_a)
        self.client.post(
            reverse("meta_conversions:settings"),
            {"access_token": "token-a", "test_event_code": ""},
        )

        settings_b = MetaConversionSettings.objects.get(tenant=self.tenant_b)
        self.assertEqual(settings_b.access_token, "token-b")
