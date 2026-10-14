import uuid

from django.test import TestCase, override_settings

from tenants.models import Tenant

from .models import User
from .oidc import CoreOIDCBackend

OIDC_SETTINGS = dict(
    OIDC_RP_CLIENT_ID="agipages-test",
    OIDC_RP_CLIENT_SECRET="x",
    OIDC_OP_AUTHORIZATION_ENDPOINT="https://id.example/o/authorize/",
    OIDC_OP_TOKEN_ENDPOINT="https://id.example/o/token/",
    OIDC_OP_USER_ENDPOINT="https://id.example/o/userinfo/",
    OIDC_OP_JWKS_ENDPOINT="https://id.example/o/.well-known/jwks.json",
    OIDC_RP_SIGN_ALGO="RS256",
)


def claims(email, sub=None, staff=False, client=None):
    memberships = []
    if client:
        memberships.append({
            "scope": "client", "whitelabel_id": str(uuid.uuid4()), "whitelabel_slug": "agitare",
            "client_id": client[0], "client_slug": client[1], "client_name": client[2], "role": "owner",
        })
    return {"sub": sub or str(uuid.uuid4()), "email": email, "given_name": "Ana", "family_name": "Lima",
            "agitare_staff": staff, "memberships": memberships}


@override_settings(**OIDC_SETTINGS)
class CoreOIDCBackendTests(TestCase):
    def setUp(self):
        self.backend = CoreOIDCBackend()

    def login(self, c):
        """What mozilla-django-oidc does after validating the tokens."""
        if not self.backend.verify_claims(c):
            return None
        users = self.backend.filter_users_by_claims(c)
        if len(users) == 1:
            return self.backend.update_user(users[0], c)
        return self.backend.create_user(c)

    def test_existing_local_user_and_tenant_are_linked_not_duplicated(self):
        tenant = Tenant.objects.create(name="Alberto Kappel", slug="albertokappel")
        local = User.objects.create_user(username="kappel", email="albertokappel@agitare.com.br", password="x")
        core_client = str(uuid.uuid4())
        user = self.login(claims("AlbertoKappel@agitare.com.br", client=(core_client, "albertokappel", "Alberto Kappel")))
        self.assertEqual(user.pk, local.pk)
        self.assertEqual(User.objects.count(), 1)
        tenant.refresh_from_db()
        self.assertEqual(str(tenant.core_uuid), core_client)
        self.assertEqual(user.tenant, tenant)
        self.assertTrue(user.check_password("x"))  # local password untouched

    def test_client_only_in_core_gets_a_new_local_tenant(self):
        core_client = str(uuid.uuid4())
        user = self.login(claims("amoapraia@agitare.com.br", client=(core_client, "amoapraia", "Amo a Praia")))
        self.assertEqual(user.tenant.slug, "amoapraia")
        self.assertEqual(str(user.tenant.core_uuid), core_client)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)

    def test_next_login_finds_the_user_by_sub_even_with_a_new_email(self):
        sub, client = str(uuid.uuid4()), (str(uuid.uuid4()), "peretto", "Peretto")
        first = self.login(claims("peretto@agitare.com.br", sub=sub, client=client))
        second = self.login(claims("contato@peretto.com.br", sub=sub, client=client))
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.email, "contato@peretto.com.br")
        self.assertEqual(Tenant.objects.count(), 1)

    def test_core_rename_updates_the_local_tenant_name(self):
        client_id, sub = str(uuid.uuid4()), str(uuid.uuid4())
        self.login(claims("a@x.com", sub=sub, client=(client_id, "sol", "Pousada Sol")))
        self.login(claims("a@x.com", sub=sub, client=(client_id, "sol", "Pousada do Sol")))
        self.assertEqual(Tenant.objects.get().name, "Pousada do Sol")

    def test_without_client_membership_the_login_is_refused(self):
        self.assertIsNone(self.login(claims("ninguem@x.com")))
        self.assertEqual(User.objects.count(), 0)

    def test_agitare_staff_gets_support_access(self):
        user = self.login(claims("leoduarte@ipmasters.com.br", staff=True))
        self.assertTrue(user.is_staff and user.is_superuser)
        self.assertIsNone(user.tenant)

    def test_linked_users_are_not_matched_by_email_again(self):
        # A local account already linked to another core person must not be
        # taken over by someone who now has that e-mail in the core.
        User.objects.create_user(username="x", email="a@x.com", password="x", core_uuid=uuid.uuid4())
        self.assertIsNone(self.login(claims("a@x.com", client=(str(uuid.uuid4()), "t", "T"))))
        self.assertEqual(User.objects.count(), 1)
