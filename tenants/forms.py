from django import forms

from .models import Tenant


class DomainForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ["custom_domain"]

    def clean_custom_domain(self):
        domain = (self.cleaned_data.get("custom_domain") or "").strip().lower()
        if not domain:
            return domain
        if (
            Tenant.objects.exclude(pk=self.instance.pk)
            .filter(custom_domain=domain)
            .exists()
        ):
            raise forms.ValidationError("Este domínio já está em uso por outra conta.")
        return domain
