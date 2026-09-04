from django.conf import settings
from django.db import models


class Lead(models.Model):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"
    STATUS_CHOICES = [
        (NEW, "Novo"),
        (CONTACTED, "Contatado"),
        (QUALIFIED, "Qualificado"),
        (CONVERTED, "Convertido"),
        (LOST, "Perdido"),
    ]

    # Denormalized onto Lead (not just via landing_page) so tenant-wide
    # queries never need a join, and so tenant filtering stays a single
    # simple `.filter(tenant=...)` everywhere leads are queried.
    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="leads"
    )
    landing_page = models.ForeignKey(
        "landingpages.LandingPage", on_delete=models.CASCADE, related_name="leads"
    )

    name = models.CharField(max_length=255)
    # Opcionais no schema porque LandingPage.show_email/show_phone permitem
    # ao tenant desligar qualquer um dos dois (ex: página só com WhatsApp,
    # sem e-mail) — a obrigatoriedade real é decidida em tempo de submissão
    # pelo form dinâmico (leads/forms.py::build_lead_capture_form).
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=100)
    # Respostas dos campos extras configurados em LandingPageFormField,
    # chaveadas por field_key. Congelado no momento da submissão: continua
    # válido mesmo se o campo correspondente for depois editado/apagado.
    extra_field_values = models.JSONField(
        "Respostas de campos personalizados", default=dict, blank=True
    )

    utm_source = models.CharField(max_length=255, blank=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True)
    utm_term = models.CharField(max_length=255, blank=True)
    utm_content = models.CharField(max_length=255, blank=True)
    gclid = models.CharField(max_length=255, blank=True)
    fbclid = models.CharField(max_length=255, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    # Meta Pixel's own first-party cookies, captured server-side for the
    # Conversions API (meta_conversions/services.py) — improves Meta's
    # match quality between the browser and server "Lead" events.
    fbp = models.CharField(max_length=255, blank=True)
    fbc = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NEW)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.landing_page.title})"


class LeadStatusHistory(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="status_history")
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name_plural = "lead status histories"

    def __str__(self):
        return f"{self.lead_id}: {self.old_status} -> {self.new_status}"
