from django.db import models


class MetaConversionSettings(models.Model):
    tenant = models.OneToOneField(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="meta_conversion_settings"
    )
    access_token = models.CharField(
        "Access Token da Conversions API",
        max_length=512,
        blank=True,
        help_text=(
            "Gerado no Business Manager da Meta em "
            "Eventos > Configurações > API de Conversões."
        ),
    )
    test_event_code = models.CharField(
        "Código de teste de eventos",
        max_length=64,
        blank=True,
        help_text=(
            "Opcional. Cole o código do painel \"Testar eventos\" do Meta Events "
            "Manager para validar o envio sem misturar com dados reais. Remova "
            "depois de testar."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversions API de {self.tenant.name}"
