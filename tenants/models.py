import secrets

from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    custom_domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    domain_verified = models.BooleanField(default=False)
    domain_verification_token = models.CharField(max_length=64, blank=True)
    domain_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.domain_verification_token:
            self.domain_verification_token = secrets.token_hex(16)
        super().save(*args, **kwargs)
