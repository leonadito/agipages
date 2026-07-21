from django import forms

from .models import Lead


class LeadCaptureForm(forms.ModelForm):
    # Honeypot: a real visitor never sees or fills this field (hidden via
    # CSS in the template); bots that auto-fill every input do. Any value
    # here means spam — reject silently, don't create a Lead.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Lead
        fields = ["name", "email", "phone", "city"]

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Envio inválido.")
        return value
