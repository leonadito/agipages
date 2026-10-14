from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from landingpages.models import LandingPage
from tenants.models import Tenant

from .models import Lead, LeadStatusHistory

User = get_user_model()


class LeadCaptureRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(name="Diamond Towers", slug="diamond-towers")
        self.page = LandingPage.objects.create(
            tenant=self.tenant,
            title="Casas em Tramandaí",
            status=LandingPage.PUBLISHED,
            hero_title="Casas em Tramandaí",
            lead_form_heading="Receba informações",
        )
        self.url = reverse(
            "public_page",
            kwargs={"tenant_slug": self.tenant.slug, "page_slug": self.page.slug},
        )

    def _post(self, suffix, **extra):
        return self.client.post(
            self.url,
            {
                "name": f"Lead {suffix}",
                "email": f"lead{suffix}@example.com",
                "phone": "51999999999",
                "city": "Torres",
                "website": "",
            },
            **extra,
        )

    def test_submissions_beyond_the_limit_are_rejected(self):
        # Rate limit is 5/min/IP (see @ratelimit on public_page). The 6th
        # POST from the same IP within the window must be blocked — this
        # is the anti-spam safeguard from PRD §7.5, exercised end-to-end
        # rather than just unit-testing the decorator config.
        responses = [self._post(i) for i in range(1, 7)]
        status_codes = [r.status_code for r in responses]
        self.assertEqual(status_codes[:5], [200] * 5)
        self.assertEqual(status_codes[5], 403)
        self.assertEqual(Lead.objects.count(), 5)

    def test_form_ships_handler_that_shows_rejected_submissions(self):
        # HTMX 1.9 drops 4xx/5xx responses; without the handler in the lead
        # form partial a rejected submission shows nothing to the visitor.
        response = self.client.get(self.url)
        self.assertContains(response, "htmx:beforeSwap")
        self.assertContains(response, "htmx:responseError")

    def test_invalid_submission_still_returns_400_with_errors(self):
        response = self.client.post(self.url, {"name": "", "phone": "", "city": "", "website": ""})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "lead-form-wrapper", status_code=400)
        self.assertEqual(Lead.objects.count(), 0)

    @override_settings(TRUSTED_PROXY_CIDRS=["172.16.0.0/12"])
    def test_behind_proxy_the_limit_is_per_visitor_not_global(self):
        # In production every request reaches Django from the Docker gateway;
        # the limit must follow the visitor IP sent by Traefik (X-Real-Ip),
        # or one busy visitor would block everyone else's leads.
        proxy = {"REMOTE_ADDR": "172.20.0.1"}
        first_visitor = [
            self._post(i, HTTP_X_REAL_IP="179.98.148.47", **proxy).status_code for i in range(1, 7)
        ]
        self.assertEqual(first_visitor, [200] * 5 + [403])

        other_visitor = self._post(7, HTTP_X_REAL_IP="200.160.2.3", **proxy)
        self.assertEqual(other_visitor.status_code, 200)
        self.assertEqual(
            Lead.objects.get(name="Lead 7").ip_address, "200.160.2.3"
        )


class LeadDashboardTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a")
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b")
        self.user_a = User.objects.create_user(
            username="usuarioa", email="a@example.com", password="SenhaForte123", tenant=self.tenant_a
        )
        self.page_a1 = LandingPage.objects.create(tenant=self.tenant_a, title="Página A1")
        self.page_a2 = LandingPage.objects.create(tenant=self.tenant_a, title="Página A2")
        self.page_b = LandingPage.objects.create(tenant=self.tenant_b, title="Página B")

        self.lead_a1 = Lead.objects.create(
            tenant=self.tenant_a,
            landing_page=self.page_a1,
            name="Lead A1",
            email="leada1@example.com",
            phone="1",
            city="Torres",
            utm_source="facebook",
            status=Lead.NEW,
        )
        self.lead_a2 = Lead.objects.create(
            tenant=self.tenant_a,
            landing_page=self.page_a2,
            name="Lead A2",
            email="leada2@example.com",
            phone="2",
            city="Torres",
            utm_source="google",
            status=Lead.CONTACTED,
        )
        self.lead_b = Lead.objects.create(
            tenant=self.tenant_b,
            landing_page=self.page_b,
            name="Lead B",
            email="leadb@example.com",
            phone="3",
            city="Outra",
            status=Lead.NEW,
        )

    def test_list_only_shows_own_tenant_leads(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("leads:list"))
        self.assertContains(response, "Lead A1")
        self.assertContains(response, "Lead A2")
        self.assertNotContains(response, "Lead B")

    def test_filter_by_landing_page(self):
        self.client.force_login(self.user_a)
        response = self.client.get(
            reverse("leads:list"), {"landing_page": self.page_a1.pk}
        )
        self.assertContains(response, "Lead A1")
        self.assertNotContains(response, "Lead A2")

    def test_filter_by_status(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("leads:list"), {"status": Lead.CONTACTED})
        self.assertContains(response, "Lead A2")
        self.assertNotContains(response, "Lead A1")

    def test_filter_by_utm_source(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("leads:list"), {"utm_source": "facebook"})
        self.assertContains(response, "Lead A1")
        self.assertNotContains(response, "Lead A2")

    def test_landing_page_filter_cannot_leak_other_tenant_leads(self):
        # Even if a user crafts landing_page=<other tenant's page id>, the
        # base queryset is already scoped to their own tenant, so no leak.
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("leads:list"), {"landing_page": self.page_b.pk})
        self.assertNotContains(response, "Lead B")

    def test_csv_export_respects_filters_and_tenant_scope(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("leads:export"), {"utm_source": "facebook"})
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("Lead A1", content)
        self.assertNotIn("Lead A2", content)
        self.assertNotIn("Lead B", content)

    def test_csv_export_includes_extra_fields_column(self):
        self.lead_a1.extra_field_values = {"interesse": "Compra"}
        self.lead_a1.save()
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("leads:export"))
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("Campos Extras", content)
        self.assertIn("interesse: Compra", content)

    def test_detail_view_renders_extra_field_values(self):
        self.lead_a1.extra_field_values = {"interesse": "Compra"}
        self.lead_a1.save()
        self.client.force_login(self.user_a)
        response = self.client.get(
            reverse("leads:detail", kwargs={"pk": self.lead_a1.pk})
        )
        self.assertContains(response, "interesse")
        self.assertContains(response, "Compra")

    def test_inline_status_update_writes_history(self):
        self.client.force_login(self.user_a)
        response = self.client.post(
            reverse("leads:update_status", kwargs={"pk": self.lead_a1.pk}),
            {"status": Lead.QUALIFIED},
        )
        self.assertEqual(response.status_code, 200)
        self.lead_a1.refresh_from_db()
        self.assertEqual(self.lead_a1.status, Lead.QUALIFIED)
        history = LeadStatusHistory.objects.get(lead=self.lead_a1)
        self.assertEqual(history.old_status, Lead.NEW)
        self.assertEqual(history.new_status, Lead.QUALIFIED)
        self.assertEqual(history.changed_by, self.user_a)

    def test_cannot_view_or_update_another_tenants_lead(self):
        self.client.force_login(self.user_a)

        detail_response = self.client.get(
            reverse("leads:detail", kwargs={"pk": self.lead_b.pk})
        )
        self.assertEqual(detail_response.status_code, 404)

        status_response = self.client.post(
            reverse("leads:update_status", kwargs={"pk": self.lead_b.pk}),
            {"status": Lead.LOST},
        )
        self.assertEqual(status_response.status_code, 404)
        self.lead_b.refresh_from_db()
        self.assertEqual(self.lead_b.status, Lead.NEW)


class LeadSignalsSkipLoaddataTests(TestCase):
    """Copying data between databases (dumpdata/loaddata, as in the move to
    Postgres) must not re-send e-mail, Telegram, Meta CAPI or Google Forms
    for leads that already existed."""

    SERVICES = [
        "email_notifications.signals.send_lead_notification_email",
        "google_forms_integration.signals.send_lead_to_google_form",
        "meta_conversions.signals.send_lead_conversion_event",
        "telegram_integration.signals.notify_new_lead",
    ]

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T", slug="t")
        self.page = LandingPage.objects.create(tenant=self.tenant, title="P")

    def _patched(self):
        from contextlib import ExitStack
        from unittest import mock

        stack = ExitStack()
        mocks = [stack.enter_context(mock.patch(path)) for path in self.SERVICES]
        return stack, mocks

    def test_normal_creation_notifies_and_loaddata_does_not(self):
        import os
        import tempfile

        from django.core import serializers
        from django.core.management import call_command

        stack, mocks = self._patched()
        with stack:
            lead = Lead.objects.create(
                tenant=self.tenant, landing_page=self.page, name="Ana", phone="1", city="Torres"
            )
            self.assertTrue(all(m.call_count == 1 for m in mocks))
            data = serializers.serialize("json", [lead])
            Lead.objects.all().delete()
            for m in mocks:
                m.reset_mock()

            fd, path = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w") as f:
                f.write(data)
            try:
                call_command("loaddata", path, verbosity=0)
            finally:
                os.remove(path)

            self.assertEqual(Lead.objects.count(), 1)
            for m in mocks:
                m.assert_not_called()
