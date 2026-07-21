from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tenants.models import Tenant

User = get_user_model()


class SignupLoginFlowTests(TestCase):
    def test_signup_creates_tenant_and_user_and_logs_in(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "tenant_name": "Kappel Imóveis",
                "email": "corretor@example.com",
                "password1": "S3nhaForte123",
                "password2": "S3nhaForte123",
            },
        )
        self.assertRedirects(response, reverse("core:dashboard"))
        user = User.objects.get(email="corretor@example.com")
        self.assertIsNotNone(user.tenant_id)
        self.assertEqual(Tenant.objects.count(), 1)

        dashboard = self.client.get(reverse("core:dashboard"))
        self.assertEqual(dashboard.status_code, 200)

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "tenant_name": "Kappel Imóveis",
                "email": "corretor@example.com",
                "password1": "S3nhaForte123",
                "password2": "OutraSenha456",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="corretor@example.com").exists())

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_logout_redirects_to_login_and_dashboard_becomes_unreachable(self):
        tenant = Tenant.objects.create(name="T1", slug="t1")
        user = User.objects.create_user(
            email="a@example.com", password="S3nhaForte123", tenant=tenant
        )
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))

        dashboard = self.client.get(reverse("core:dashboard"))
        self.assertEqual(dashboard.status_code, 302)
