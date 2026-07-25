import secrets

from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    custom_domain = models.CharField(
        "Domínio próprio",
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Ex: meusite.com.br (sem http:// e sem barra no final)",
    )
    domain_verified = models.BooleanField("Domínio verificado", default=False)
    domain_verification_token = models.CharField(max_length=64, blank=True)
    domain_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def dns_challenge_host(self):
        """Hostname where the TXT ownership-proof record must be created.

        Derived (not stored) so there's a single source of truth shared by
        the verification service and the dashboard instructions template.
        """
        if not self.custom_domain:
            return None
        return f"_agipages-challenge.{self.custom_domain}"

    def save(self, *args, **kwargs):
        if self.pk:
            old_domain = (
                Tenant.objects.filter(pk=self.pk)
                .values_list("custom_domain", flat=True)
                .first()
            )
            if old_domain != self.custom_domain:
                # Domain changed (or cleared) — the old token no longer
                # proves anything and any prior verification is invalid.
                self.domain_verification_token = secrets.token_hex(16)
                self.domain_verified = False
                self.domain_verified_at = None
        if not self.domain_verification_token:
            self.domain_verification_token = secrets.token_hex(16)
        super().save(*args, **kwargs)
