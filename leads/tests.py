from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
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

    def _post(self, suffix):
        return self.client.post(
            self.url,
            {
                "name": f"Lead {suffix}",
                "email": f"lead{suffix}@example.com",
                "phone": "51999999999",
                "city": "Torres",
                "website": "",
            },
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
