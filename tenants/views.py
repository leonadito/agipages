from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from core.mixins import TenantDashboardMixin

from .forms import DomainForm
from .services import verify_domain_ownership


class DomainSettingsView(TenantDashboardMixin, View):
    template_name = "tenants/domain.html"

    def get(self, request):
        return self._render(request, DomainForm(instance=self.tenant))

    def post(self, request):
        form = DomainForm(request.POST, instance=self.tenant)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Domínio salvo. Siga as instruções abaixo para verificar a propriedade.",
            )
            return redirect("tenants:domain")
        return self._render(request, form)

    def _render(self, request, form):
        return render(request, self.template_name, {"form": form, "tenant": self.tenant})


class DomainVerifyView(TenantDashboardMixin, View):
    def post(self, request):
        success, error = verify_domain_ownership(self.tenant)
        if success:
            messages.success(request, "Domínio verificado com sucesso!")
        else:
            messages.error(request, error)
        return redirect("tenants:domain")
