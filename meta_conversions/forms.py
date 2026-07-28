from django import forms

from .models import MetaConversionSettings


class MetaConversionSettingsForm(forms.ModelForm):
    class Meta:
        model = MetaConversionSettings
        fields = ["access_token", "test_event_code"]
