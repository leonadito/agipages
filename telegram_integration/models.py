import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone


class TelegramIntegration(models.Model):
    tenant = models.OneToOneField(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="telegram_integration"
    )
    chat_id = models.CharField(max_length=64, blank=True)
    linked_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"Telegram de {self.tenant.name}"


class TelegramLinkCode(models.Model):
    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="telegram_link_codes"
    )
    code = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.tenant.name}: {self.code}"

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at

    @classmethod
    def generate_for(cls, tenant, ttl_minutes=10):
        return cls.objects.create(
            tenant=tenant,
            code=secrets.token_urlsafe(8),
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
