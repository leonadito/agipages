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
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    city = models.CharField(max_length=100)

    utm_source = models.CharField(max_length=255, blank=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True)
    utm_term = models.CharField(max_length=255, blank=True)
    utm_content = models.CharField(max_length=255, blank=True)
    gclid = models.CharField(max_length=255, blank=True)
    fbclid = models.CharField(max_length=255, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

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
