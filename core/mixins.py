from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class TenantDashboardMixin(LoginRequiredMixin):
    """Base mixin for every dashboard view.

    The tenant is ALWAYS derived from `request.user.tenant` (the
    session-authenticated user) — never from a URL segment. This is the
    single most important isolation rule in the whole system (PRD §8):
    the public site's tenant slug in the URL is routing only, and the
    dashboard must never trust it. Views combine this with
    `get_queryset()`/`get_object()` filtering by `self.tenant` so one
    tenant can never read or write another tenant's data.
    """

    tenant = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.tenant_id is None:
                raise PermissionDenied("Usuário não pertence a nenhum tenant.")
            self.tenant = request.user.tenant
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenant"] = self.tenant
        return context
