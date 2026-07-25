from unittest.mock import patch

import dns.exception
import dns.resolver
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User

from .middleware import TenantResolutionMiddleware
from .models import Tenant
from .services import verify_domain_ownership
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


class _FakeTXTRdata:
    def __init__(self, value):
        self.strings = [value.encode("utf-8")]


class TenantSaveTokenRotationTests(TestCase):
    def test_changing_domain_rotates_token_and_resets_verification(self):
        tenant = Tenant.objects.create(name="Tenant A", slug="tenant-a", custom_domain="old.com.br")
        tenant.domain_verified = True
        tenant.save()
        old_token = tenant.domain_verification_token

        tenant.custom_domain = "new.com.br"
        tenant.save()

        self.assertNotEqual(tenant.domain_verification_token, old_token)
        self.assertFalse(tenant.domain_verified)
        self.assertIsNone(tenant.domain_verified_at)

    def test_unchanged_domain_keeps_token_and_verification(self):
        tenant = Tenant.objects.create(name="Tenant A", slug="tenant-a", custom_domain="same.com.br")
        tenant.domain_verified = True
        tenant.save()
        old_token = tenant.domain_verification_token

        tenant.name = "Tenant A Renamed"
        tenant.save()

        self.assertEqual(tenant.domain_verification_token, old_token)
        self.assertTrue(tenant.domain_verified)


class DomainVerificationServiceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Tenant A", slug="tenant-a", custom_domain="meudominio.com.br"
        )

    @patch("tenants.services.dns.resolver.Resolver.resolve")
    def test_matching_txt_record_verifies_domain(self, mock_resolve):
        mock_resolve.return_value = [_FakeTXTRdata(self.tenant.domain_verification_token)]
        success, error = verify_domain_ownership(self.tenant)
        self.assertTrue(success)
        self.assertIsNone(error)
        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.domain_verified)
        self.assertIsNotNone(self.tenant.domain_verified_at)

    @patch("tenants.services.dns.resolver.Resolver.resolve")
    def test_mismatched_txt_record_does_not_verify(self, mock_resolve):
        mock_resolve.return_value = [_FakeTXTRdata("valor-errado")]
        success, error = verify_domain_ownership(self.tenant)
        self.assertFalse(success)
        self.assertIsNotNone(error)
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.domain_verified)

    @patch("tenants.services.dns.resolver.Resolver.resolve", side_effect=dns.resolver.NXDOMAIN())
    def test_nxdomain_does_not_raise(self, mock_resolve):
        success, error = verify_domain_ownership(self.tenant)
        self.assertFalse(success)
        self.assertIsNotNone(error)

    @patch("tenants.services.dns.resolver.Resolver.resolve", side_effect=dns.exception.Timeout())
    def test_timeout_does_not_raise(self, mock_resolve):
        success, error = verify_domain_ownership(self.tenant)
        self.assertFalse(success)
        self.assertIsNotNone(error)

    def test_no_custom_domain_returns_friendly_error(self):
        tenant = Tenant.objects.create(name="Sem domínio", slug="sem-dominio")
        success, error = verify_domain_ownership(tenant)
        self.assertFalse(success)
        self.assertIsNotNone(error)


class DomainSettingsViewTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a")
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", custom_domain="b.com.br")
        self.user_a = User.objects.create_user(
            username="usuarioa", email="a@example.com", password="SenhaForte123", tenant=self.tenant_a
        )
        self.user_b = User.objects.create_user(
            username="usuariob", email="b@example.com", password="SenhaForte123", tenant=self.tenant_b
        )

    def test_saving_domain_only_affects_own_tenant(self):
        self.client.force_login(self.user_a)
        response = self.client.post(reverse("tenants:domain"), {"custom_domain": "a.com.br"})
        self.assertEqual(response.status_code, 302)

        self.tenant_a.refresh_from_db()
        self.tenant_b.refresh_from_db()
        self.assertEqual(self.tenant_a.custom_domain, "a.com.br")
        self.assertEqual(self.tenant_b.custom_domain, "b.com.br")

    def test_cannot_reuse_domain_already_taken_by_another_tenant(self):
        self.client.force_login(self.user_a)
        response = self.client.post(reverse("tenants:domain"), {"custom_domain": "b.com.br"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "já está em uso")
        self.tenant_a.refresh_from_db()
        self.assertNotEqual(self.tenant_a.custom_domain, "b.com.br")

    @patch("tenants.services.dns.resolver.Resolver.resolve")
    def test_verify_view_only_verifies_own_tenant(self, mock_resolve):
        mock_resolve.return_value = [_FakeTXTRdata(self.tenant_b.domain_verification_token)]
        self.client.force_login(self.user_b)
        response = self.client.post(reverse("tenants:domain_verify"))
        self.assertEqual(response.status_code, 302)

        self.tenant_a.refresh_from_db()
        self.tenant_b.refresh_from_db()
        self.assertTrue(self.tenant_b.domain_verified)
        self.assertFalse(self.tenant_a.domain_verified)
