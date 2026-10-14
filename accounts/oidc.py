"""Single sign-on with the Agitare Core (OIDC provider).

Enabled only when OIDC_RP_CLIENT_ID is set (see config/settings/base.py), so
production keeps its local login until the cutover.

Identity rules:
- a local user is linked to the core person by `core_uuid` (the OIDC `sub`);
  on the first SSO login an existing local user with the same e-mail is
  linked instead of creating a duplicate;
- staff/superuser follow the core's `agitare_staff` claim;
- the tenants a person may use come from the memberships: a client
  membership gives that client; an agency membership gives the agency's own
  tenant and all its active clients (listed in the claim). Each local Tenant
  is linked by `core_uuid`, else by slug, else created from the claim. The
  list goes to the session ("tenant_choices") for the tenant selector
  (accounts/tenant_switch.py); user.tenant is the one currently selected.
  People with no tenant at all (and not Agitare staff) are refused.
"""
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from tenants.models import Tenant

logger = logging.getLogger(__name__)


def accessible_clients(claims):
    """Every core client this person may use here, in claim order, as dicts
    shaped like a client membership (client_id, client_slug, client_name)."""
    seen, out = set(), []
    for m in claims.get("memberships") or []:
        if m.get("scope") == "client" and m.get("client_id"):
            entries = [m]
        elif m.get("scope") == "whitelabel":
            entries = [
                {"client_id": c["id"], "client_slug": c.get("slug"), "client_name": c.get("name")}
                for c in m.get("clients") or []
            ]
        else:
            entries = []
        for e in entries:
            if e["client_id"] not in seen:
                seen.add(e["client_id"])
                out.append(e)
    return out


def tenant_for_membership(membership):
    """Local Tenant for a core client: by core_uuid, else by slug (and link
    it), else a new tenant created from the claim."""
    core_id = membership["client_id"]
    tenant = Tenant.objects.filter(core_uuid=core_id).first()
    if tenant:
        if membership.get("client_name") and tenant.name != membership["client_name"]:
            tenant.name = membership["client_name"]
            tenant.save(update_fields=["name", "updated_at"])
        return tenant
    slug = membership.get("client_slug") or ""
    tenant = Tenant.objects.filter(slug=slug, core_uuid__isnull=True).first() if slug else None
    if tenant:
        tenant.core_uuid = core_id
        tenant.save(update_fields=["core_uuid", "updated_at"])
        return tenant
    return Tenant.objects.create(
        name=membership.get("client_name") or slug,
        slug=slug or slugify(membership.get("client_name") or core_id)[:100],
        core_uuid=core_id,
    )


class CoreOIDCBackend(OIDCAuthenticationBackend):
    def verify_claims(self, claims):
        if not super().verify_claims(claims) or not claims.get("sub"):
            return False
        email = (claims.get("email") or "").strip()
        taken = (
            self.UserModel.objects.filter(email__iexact=email, core_uuid__isnull=False)
            .exclude(core_uuid=claims["sub"])
            .exists()
        )
        if email and taken:
            # Never take over a local account linked to another core person.
            logger.warning("Login único recusado: %s já pertence a outra pessoa do core", email)
            return False
        if claims.get("agitare_staff") or accessible_clients(claims):
            return True
        logger.warning("Login único recusado: %s sem nenhum tenant no core", claims.get("email"))
        return False

    def filter_users_by_claims(self, claims):
        users = self.UserModel.objects.filter(core_uuid=claims["sub"])
        if users.exists():
            return users
        email = (claims.get("email") or "").strip()
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email, core_uuid__isnull=True)

    def _unique_username(self, email):
        base = (email.split("@")[0] or "usuario")[:140]
        candidate, n = base, 1
        while self.UserModel.objects.filter(username=candidate).exists():
            n += 1
            candidate = f"{base}{n}"
        return candidate

    @transaction.atomic
    def create_user(self, claims):
        user = self.UserModel(
            username=self._unique_username(claims["email"]), email=claims["email"]
        )
        user.set_unusable_password()  # signs in only through the core
        return self.update_user(user, claims)

    @transaction.atomic
    def update_user(self, user, claims):
        if getattr(self, "request", None) is not None:
            # Read by accounts.backchannel at login to track this session.
            self.request.session["oidc_sub"] = claims["sub"]
        user.core_uuid = claims["sub"]
        user.email = claims.get("email") or user.email
        user.first_name = claims.get("given_name") or user.first_name
        user.last_name = claims.get("family_name") or user.last_name
        staff = bool(claims.get("agitare_staff"))
        user.is_staff = staff
        user.is_superuser = staff
        tenants = [tenant_for_membership(entry) for entry in accessible_clients(claims)]
        if tenants and (user.tenant_id not in {t.pk for t in tenants}):
            user.tenant = tenants[0]  # keep the current choice when still allowed
        user.save()
        if getattr(self, "request", None) is not None:
            self.request.session["tenant_choices"] = [str(t.core_uuid) for t in tenants]
        return user


def provider_logout(request):
    """Where the browser goes after the local logout: the core's end-session
    endpoint, so the single sign-on session ends too."""
    params = {"post_logout_redirect_uri": settings.OIDC_POST_LOGOUT_REDIRECT_URI}
    id_token = request.session.get("oidc_id_token")
    if id_token:
        params["id_token_hint"] = id_token
    params["client_id"] = settings.OIDC_RP_CLIENT_ID
    return f"{settings.OIDC_OP_LOGOUT_ENDPOINT}?{urlencode(params)}"
