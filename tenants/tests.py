from django.test import RequestFactory, TestCase

from .middleware import TenantResolutionMiddleware
from .models import Tenant


class TenantResolutionMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantResolutionMiddleware(lambda request: None)
        self.tenant = Tenant.objects.create(
            name="Diamond Towers",
            slug="diamond-towers",
            custom_domain="diamondtowers.example.com",
            domain_verified=True,
        )

    def test_verified_custom_domain_resolves_tenant_and_swaps_urlconf(self):
        request = self.factory.get("/", HTTP_HOST="diamondtowers.example.com")
        self.middleware(request)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.urlconf, "config.urls_custom_domain")

    def test_custom_domain_with_port_is_matched_ignoring_port(self):
        request = self.factory.get("/", HTTP_HOST="diamondtowers.example.com:8000")
        self.middleware(request)
        self.assertEqual(request.tenant, self.tenant)

    def test_unverified_custom_domain_does_not_resolve(self):
        self.tenant.domain_verified = False
        self.tenant.save()
        request = self.factory.get("/", HTTP_HOST="diamondtowers.example.com")
        self.middleware(request)
        self.assertIsNone(request.tenant)
        self.assertFalse(hasattr(request, "urlconf"))

    def test_platform_host_does_not_resolve_tenant(self):
        request = self.factory.get("/", HTTP_HOST="meusaas.example.com")
        self.middleware(request)
        self.assertIsNone(request.tenant)
        self.assertFalse(hasattr(request, "urlconf"))
