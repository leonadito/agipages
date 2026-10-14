"""Tenant selector for people with more than one tenant (agency staff: their
own tenant plus their clients; Agitare staff: every tenant, for support).

The allowed tenants come from the core at login (session "tenant_choices",
see accounts/oidc.py). The dashboard keeps deriving the tenant from
request.user.tenant everywhere; switching just changes that field, and only
to a tenant the person is allowed to use.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from tenants.models import Tenant


def allowed_tenants(request):
    user = request.user
    if not user.is_authenticated:
        return Tenant.objects.none()
    if user.is_superuser:
        return Tenant.objects.all()
    choices = request.session.get("tenant_choices") or []
    return Tenant.objects.filter(core_uuid__in=choices)


@login_required
@require_POST
def switch_tenant(request):
    tenant = get_object_or_404(Tenant, pk=request.POST.get("tenant"))
    if not allowed_tenants(request).filter(pk=tenant.pk).exists():
        return HttpResponseForbidden("Você não tem acesso a este cliente.")
    request.user.tenant = tenant
    request.user.save(update_fields=["tenant"])
    return redirect("landingpages:list")


def tenant_switcher(request):
    """Context processor: the selector shows only with two or more choices."""
    choices = list(allowed_tenants(request).order_by("name")) if hasattr(request, "user") else []
    return {"tenant_choices": choices if len(choices) > 1 else []}
