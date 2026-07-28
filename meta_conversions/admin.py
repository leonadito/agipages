from django.contrib import admin

from .models import MetaConversionSettings


@admin.register(MetaConversionSettings)
class MetaConversionSettingsAdmin(admin.ModelAdmin):
    list_display = ("tenant", "updated_at")
