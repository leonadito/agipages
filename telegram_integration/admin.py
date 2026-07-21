from django.contrib import admin

from .models import TelegramIntegration, TelegramLinkCode


@admin.register(TelegramIntegration)
class TelegramIntegrationAdmin(admin.ModelAdmin):
    list_display = ("tenant", "chat_id", "is_active", "linked_at")


@admin.register(TelegramLinkCode)
class TelegramLinkCodeAdmin(admin.ModelAdmin):
    list_display = ("tenant", "code", "used", "expires_at")
