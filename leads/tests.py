from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from landingpages.models import LandingPage
from tenants.models import Tenant

from .models import Lead


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
