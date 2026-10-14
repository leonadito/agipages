import uuid

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings

from tenants.models import Tenant

from .models import User
from .oidc import CoreOIDCBackend
from .tenant_switch import tenant_switcher
from .tests_oidc import OIDC_SETTINGS


def agency_claims(email, own, clients, sub=None):
    return {
        "sub": sub or str(uuid.uuid4()), "email": email, "agitare_staff": False,
        "memberships": [{
            "scope": "whitelabel", "whitelabel_id": str(uuid.uuid4()), "whitelabel_slug": "alfa",
            "client_id": None, "role": "owner",
            "clients": [{"id": cid, "slug": slug, "name": name} for cid, slug, name in [own, *clients]],
        }],
    }


@override_settings(**OIDC_SETTINGS)
class AgencyLoginTests(TestCase):
    def setUp(self):
        self.backend = CoreOIDCBackend()
        self.backend.request = RequestFactory().get("/")
        self.backend.request.session = SessionStore()
        self.own = (str(uuid.uuid4()), "alfa", "Agência Alfa")
        self.c1 = (str(uuid.uuid4()), "pousada", "Pousada")
        self.c2 = (str(uuid.uuid4()), "imobiliaria", "Imobiliária")

    def login(self, claims):
        self.assertTrue(self.backend.verify_claims(claims))
        users = self.backend.filter_users_by_claims(claims)
        return self.backend.update_user(users[0], claims) if len(users) == 1 else self.backend.create_user(claims)

    def test_agency_person_gets_own_tenant_and_clients(self):
        Tenant.objects.create(name="Pousada antiga", slug="pousada")  # already in the app: linked by slug
        user = self.login(agency_claims("dona@alfa.com", self.own, [self.c1, self.c2]))
        self.assertEqual(user.tenant.slug, "alfa")  # own tenant first
        self.assertEqual(Tenant.objects.count(), 3)
        self.assertEqual(
            sorted(self.backend.request.session["tenant_choices"]),
            sorted([self.own[0], self.c1[0], self.c2[0]]),
        )

    def test_next_login_keeps_the_selected_client(self):
        sub = str(uuid.uuid4())
        user = self.login(agency_claims("dona@alfa.com", self.own, [self.c1], sub=sub))
        user.tenant = Tenant.objects.get(slug="pousada")
        user.save()
        user = self.login(agency_claims("dona@alfa.com", self.own, [self.c1], sub=sub))
        self.assertEqual(user.tenant.slug, "pousada")

    def test_selected_client_that_left_the_agency_falls_back(self):
        sub = str(uuid.uuid4())
        user = self.login(agency_claims("dona@alfa.com", self.own, [self.c1], sub=sub))
        user.tenant = Tenant.objects.get(slug="pousada")
        user.save()
        user = self.login(agency_claims("dona@alfa.com", self.own, [], sub=sub))
        self.assertEqual(user.tenant.slug, "alfa")


class SwitchTenantViewTests(TestCase):
    def setUp(self):
        self.mine = Tenant.objects.create(name="Agência Alfa", slug="alfa", core_uuid=uuid.uuid4())
        self.client_t = Tenant.objects.create(name="Pousada", slug="pousada", core_uuid=uuid.uuid4())
        self.other = Tenant.objects.create(name="De outra agência", slug="outra", core_uuid=uuid.uuid4())
        self.user = User.objects.create_user(username="dona", email="dona@alfa.com", password="x", tenant=self.mine)

    def login_with_choices(self, user, choices):
        self.client.force_login(user)
        session = self.client.session
        session["tenant_choices"] = [str(t.core_uuid) for t in choices]
        session.save()

    def test_switches_to_an_allowed_client(self):
        self.login_with_choices(self.user, [self.mine, self.client_t])
        response = self.client.post("/accounts/tenant/", {"tenant": self.client_t.pk})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.tenant, self.client_t)

    def test_cannot_switch_to_a_tenant_outside_the_list(self):
        self.login_with_choices(self.user, [self.mine, self.client_t])
        response = self.client.post("/accounts/tenant/", {"tenant": self.other.pk})
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.tenant, self.mine)

    def test_agitare_staff_can_switch_to_any_tenant(self):
        staff = User.objects.create_superuser(username="leo", email="leo@x.com", password="x")
        self.client.force_login(staff)
        self.client.post("/accounts/tenant/", {"tenant": self.other.pk})
        staff.refresh_from_db()
        self.assertEqual(staff.tenant, self.other)

    def test_selector_only_shows_with_two_or_more_tenants(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {"tenant_choices": [str(self.mine.core_uuid)]}
        self.assertEqual(tenant_switcher(request)["tenant_choices"], [])
        request.session = {"tenant_choices": [str(self.mine.core_uuid), str(self.client_t.core_uuid)]}
        self.assertEqual(len(tenant_switcher(request)["tenant_choices"]), 2)

    def test_dashboard_shows_the_selector_bar(self):
        self.login_with_choices(self.user, [self.mine, self.client_t])
        response = self.client.get("/dashboard/")
        self.assertContains(response, 'id="tenant-switcher"')
        self.assertContains(response, "Pousada")
