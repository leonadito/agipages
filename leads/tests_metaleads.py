import json
import uuid
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from landingpages.models import LandingPage, LandingPageFormField
from tenants.models import Tenant

from .metaleads import MAX_ATTEMPTS, build_payload, page_url, send_lead_to_metaleads
from .models import Lead

ON = dict(METALEADS_API_URL="https://leads.example", METALEADS_API_TOKEN="svc", SITE_URL="https://pages.example")
TASK = "leads.metaleads.send_lead_to_metaleads"


class MetaleadsDeliveryTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Alberto", slug="albertokappel", core_uuid=uuid.uuid4())
        self.page = LandingPage.objects.create(tenant=self.tenant, title="Alto do Parque", status=LandingPage.PUBLISHED)
        LandingPageFormField.objects.create(landing_page=self.page, field_key="quartos", label="Quartos", field_type="text")

    def make_lead(self, **extra):
        return Lead.objects.create(
            tenant=self.tenant, landing_page=self.page, name="Ana", phone="51999998888", city="Torres",
            extra_field_values={"quartos": "3"}, utm_source="facebook", utm_campaign="lancamento", fbclid="fb1", **extra,
        )

    def queued(self):
        return DBTaskResult.objects.filter(task_path=TASK)

    def test_not_queued_when_off(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.make_lead()
        self.assertFalse(self.queued().exists())

    @override_settings(**ON)
    def test_new_lead_is_queued_once(self):
        with self.captureOnCommitCallbacks(execute=True):
            lead = self.make_lead()
            lead.name = "Ana Lima"
            lead.save()  # an update is not a new lead
        self.assertEqual(self.queued().count(), 1)

    @override_settings(**ON)
    def test_payload_carries_tenant_page_answers_and_attribution(self):
        lead = self.make_lead()
        p = build_payload(lead)
        self.assertEqual(p["tenant"], str(self.tenant.core_uuid))
        self.assertEqual((p["source"], p["external_id"]), ("agipages_form", str(lead.uuid)))
        self.assertEqual(p["occurred_at"], lead.created_at.isoformat())
        self.assertEqual(p["landing_page"], {"id": str(self.page.uuid), "name": "Alto do Parque",
                                             "url": f"https://pages.example/albertokappel/{self.page.slug}/"})
        self.assertEqual(p["form_answers"], {"quartos": "3"})
        att = p["attribution"]
        self.assertEqual((att["platform"], att["kind"], att["utm_campaign"], att["fbclid"]), ("meta", "landing_page", "lancamento", "fb1"))
        self.assertEqual(att["raw"]["form_labels"], {"quartos": "Quartos"})

    def test_page_url_uses_the_verified_custom_domain(self):
        # update(): Tenant.save() resets the verification when the domain changes.
        Tenant.objects.filter(pk=self.tenant.pk).update(custom_domain="albertokappel.com.br", domain_verified=True)
        self.page = LandingPage.objects.select_related("tenant").get(pk=self.page.pk)
        self.assertEqual(page_url(self.page), f"https://albertokappel.com.br/{self.page.slug}/")

    @override_settings(**ON)
    def test_success_stores_the_crm_lead_and_never_sends_twice(self):
        lead = self.make_lead()
        crm_id = str(uuid.uuid4())
        ok = mock.Mock(status_code=201, json=lambda: {"lead": crm_id})
        with mock.patch("leads.metaleads.requests.post", return_value=ok) as post:
            send_lead_to_metaleads.call(lead.pk)
            send_lead_to_metaleads.call(lead.pk)
        self.assertEqual(post.call_count, 1)
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["Idempotency-Key"], f"agipages-lead-{lead.uuid}")
        self.assertEqual(headers["Authorization"], "Bearer svc")
        lead.refresh_from_db()
        self.assertEqual(str(lead.metaleads_lead_uuid), crm_id)
        self.assertIsNotNone(lead.metaleads_sent_at)

    @override_settings(**ON)
    def test_failure_retries_later_then_gives_up(self):
        lead = self.make_lead()
        down = mock.Mock(status_code=503, text="fora")
        with mock.patch("leads.metaleads.requests.post", return_value=down):
            send_lead_to_metaleads.call(lead.pk)
        retry = self.queued().get()
        self.assertGreater(retry.run_after, timezone.now() + timedelta(seconds=50))
        lead.refresh_from_db()
        self.assertIn("HTTP 503", lead.metaleads_error)
        Lead.objects.filter(pk=lead.pk).update(metaleads_attempts=MAX_ATTEMPTS - 1)
        DBTaskResult.objects.all().delete()
        with mock.patch("leads.metaleads.requests.post", return_value=down):
            send_lead_to_metaleads.call(lead.pk)
        self.assertFalse(self.queued().exists())  # gave up

    @override_settings(**ON)
    def test_tenant_not_linked_to_the_core_waits_and_retries(self):
        self.tenant.core_uuid = None
        self.tenant.save()
        lead = self.make_lead()
        with mock.patch("leads.metaleads.requests.post") as post:
            send_lead_to_metaleads.call(lead.pk)
        post.assert_not_called()
        lead.refresh_from_db()
        self.assertIn("core_uuid", lead.metaleads_error)
        self.assertTrue(self.queued().exists())
