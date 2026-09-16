from unittest.mock import patch

import requests
from django.test import TestCase

from landingpages.models import LandingPage, LandingPageFormField
from leads.models import Lead
from tenants.models import Tenant

from .services import send_lead_to_google_form


class GoogleFormMirrorTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Alberto Kappel", slug="albertokappel")
        self.page = LandingPage.objects.create(
            tenant=self.tenant,
            title="Alto do Parque",
            status=LandingPage.PUBLISHED,
            google_form_id="abc123",
            google_form_entry_name="entry.1",
            google_form_entry_phone="entry.2",
        )
        LandingPageFormField.objects.create(
            landing_page=self.page,
            field_key="objetivo",
            label="Seu interesse é",
            google_form_entry_id="entry.3",
        )

    @patch("google_forms_integration.services.requests.post")
    def test_new_lead_mirrors_fixed_and_extra_fields_to_google_form(self, mock_post):
        lead = Lead.objects.create(
            tenant=self.tenant,
            landing_page=self.page,
            name="Maria",
            phone="51999999999",
            city="Lajeado",
            extra_field_values={"objetivo": "Investimento"},
        )

        self.assertTrue(mock_post.called)
        args, kwargs = mock_post.call_args
        self.assertEqual(
            args[0], "https://docs.google.com/forms/d/e/abc123/formResponse"
        )
        self.assertEqual(
            kwargs["data"],
            {"entry.1": "Maria", "entry.2": "51999999999", "entry.3": "Investimento"},
        )
        self.assertIsNotNone(lead.pk)

    @patch("google_forms_integration.services.requests.post", side_effect=requests.Timeout)
    def test_google_forms_timeout_does_not_raise_or_block_lead_creation(self, mock_post):
        # Same silent-failure contract as telegram_integration/meta_conversions:
        # the Lead must exist even though the mirrored request raised.
        lead = Lead.objects.create(
            tenant=self.tenant,
            landing_page=self.page,
            name="João",
            phone="51988888888",
            city="Lajeado",
        )
        self.assertIsNotNone(lead.pk)
        self.assertTrue(mock_post.called)

    def test_no_request_sent_when_google_form_id_blank(self):
        self.page.google_form_id = ""
        self.page.save(update_fields=["google_form_id"])
        with patch("google_forms_integration.services.requests.post") as mock_post:
            Lead.objects.create(
                tenant=self.tenant,
                landing_page=self.page,
                name="Sem Forms",
                phone="1",
                city="Lajeado",
            )
            mock_post.assert_not_called()

    def test_no_request_sent_when_no_field_mapped(self):
        page = LandingPage.objects.create(
            tenant=self.tenant, title="Outra página", google_form_id="xyz"
        )
        with patch("google_forms_integration.services.requests.post") as mock_post:
            Lead.objects.create(
                tenant=self.tenant,
                landing_page=page,
                name="Sem Mapeamento",
                phone="1",
                city="Lajeado",
            )
            mock_post.assert_not_called()

    @patch("google_forms_integration.services.requests.post")
    def test_send_lead_to_google_form_returns_false_without_form_id(self, mock_post):
        self.page.google_form_id = ""
        lead = Lead(
            tenant=self.tenant, landing_page=self.page, name="X", city="Lajeado"
        )
        result = send_lead_to_google_form(lead)
        self.assertFalse(result)
        mock_post.assert_not_called()
