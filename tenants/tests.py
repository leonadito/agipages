from django.test import RequestFactory, TestCase

from .middleware import TenantResolutionMiddleware
from .models import Tenant
from .traefik import build_traefik_dynamic_config


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


class TraefikDynamicConfigTests(TestCase):
    def test_verified_tenant_gets_http_and_https_routers(self):
        Tenant.objects.create(
            name="Diamond Towers",
            slug="diamond-towers",
            custom_domain="diamondtowers.com.br",
            domain_verified=True,
        )
        config = build_traefik_dynamic_config()
        routers = config["http"]["routers"]
        self.assertIn("tenant-diamond-towers-websecure", routers)
        self.assertIn("tenant-diamond-towers-web", routers)
        websecure = routers["tenant-diamond-towers-websecure"]
        self.assertEqual(websecure["rule"], "Host(`diamondtowers.com.br`)")
        self.assertEqual(websecure["service"], "web")
        self.assertEqual(websecure["tls"]["certResolver"], "letsencrypt")

    def test_unverified_or_domainless_tenants_get_no_router(self):
        Tenant.objects.create(name="No Domain", slug="no-domain")
        Tenant.objects.create(
            name="Unverified",
            slug="unverified",
            custom_domain="unverified.example.com",
            domain_verified=False,
        )
        config = build_traefik_dynamic_config()
        self.assertEqual(config["http"]["routers"], {})
