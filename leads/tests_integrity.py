import json
import uuid
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from landingpages.models import LandingPage
from tenants.models import Tenant

from .metaleads import MAX_ATTEMPTS
from .models import Lead

URL = "/api/v1/integrity/"


@override_settings(INTEGRITY_API_TOKEN="tok-integridade")
class IntegrityEndpointTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Alberto", slug="albertokappel", core_uuid=uuid.uuid4())
        self.loose = Tenant.objects.create(name="Solto", slug="solto")
        self.page = LandingPage.objects.create(tenant=self.tenant, title="Alto do Parque", status=LandingPage.PUBLISHED)
        self.draft = LandingPage.objects.create(tenant=self.loose, title="Rascunho")

    def post(self, body, token="tok-integridade"):
        return self.client.post(URL, json.dumps(body), content_type="application/json",
                                HTTP_AUTHORIZATION=f"Bearer {token}")

    def lead(self, **extra):
        return Lead.objects.create(tenant=self.tenant, landing_page=self.page, name="Ana", phone="51999998888", **extra)

    def test_needs_the_token(self):
        self.assertEqual(self.post({}, token="outro").status_code, 401)
        with override_settings(INTEGRITY_API_TOKEN=""):
            self.assertEqual(self.post({}, token="").status_code, 401)

    def test_pages_tenants_and_undelivered_leads(self):
        gone = str(uuid.uuid4())
        delivered = self.lead(metaleads_sent_at=timezone.now(), metaleads_attempts=1)
        given_up = self.lead(metaleads_attempts=MAX_ATTEMPTS, metaleads_error="HTTP 422")
        retrying_now = self.lead(metaleads_attempts=1)
        old_pending = self.lead(metaleads_attempts=2)
        Lead.objects.filter(pk=old_pending.pk).update(created_at=timezone.now() - timedelta(days=2))

        r = self.post({"pages": [str(self.page.uuid), str(self.draft.uuid), gone]})
        data = r.json()
        self.assertEqual(data["pages"], {
            str(self.page.uuid): {"status": "published", "tenant": str(self.tenant.core_uuid)},
            str(self.draft.uuid): {"status": "draft", "tenant": None},
        })
        self.assertIn({"slug": "solto", "name": "Solto", "core_uuid": None}, data["tenants"])
        undelivered = {lead["uuid"] for lead in data["undelivered_leads"]}
        self.assertEqual(undelivered, {str(given_up.uuid), str(old_pending.uuid)})
        self.assertNotIn(str(delivered.uuid), undelivered)
        self.assertNotIn(str(retrying_now.uuid), undelivered)

    def test_bad_body(self):
        self.assertEqual(self.post({"pages": ["não-é-uuid"]}).status_code, 400)
