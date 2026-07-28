from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from core.mixins import TenantDashboardMixin

from .forms import MetaConversionSettingsForm
from .models import MetaConversionSettings


class MetaConversionSettingsView(TenantDashboardMixin, View):
    template_name = "meta_conversions/settings.html"

    def get(self, request):
        conversion_settings, _ = MetaConversionSettings.objects.get_or_create(
            tenant=self.tenant
        )
        return self._render(request, MetaConversionSettingsForm(instance=conversion_settings))

    def post(self, request):
        conversion_settings, _ = MetaConversionSettings.objects.get_or_create(
            tenant=self.tenant
        )
        form = MetaConversionSettingsForm(request.POST, instance=conversion_settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração da Conversions API salva.")
            return redirect("meta_conversions:settings")
        return self._render(request, form)

    def _render(self, request, form):
        return render(request, self.template_name, {"form": form, "tenant": self.tenant})
