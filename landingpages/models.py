from django.conf import settings
from django.db import models
from django.utils.text import slugify


class LandingPage(models.Model):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [
        (DRAFT, "Rascunho"),
        (PUBLISHED, "Publicada"),
    ]

    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="landing_pages"
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)

    # 1. Hero
    hero_background_image = models.ImageField(
        upload_to="landing_pages/hero/", blank=True, null=True
    )
    hero_background_video_url = models.URLField(blank=True)
    hero_title = models.CharField(max_length=255, blank=True)
    hero_subtitle = models.CharField(max_length=500, blank=True)
    hero_cta_text = models.CharField(
        max_length=100, blank=True, default="Receba informações exclusivas"
    )
    hero_cta_target = models.CharField(max_length=100, blank=True, default="lead-form")

    # 2. Faixa de destaque
    highlight_bar_text = models.CharField(max_length=500, blank=True)

    # 4. Condições financeiras
    down_payment_text = models.CharField(max_length=255, blank=True)
    installment_text = models.CharField(max_length=255, blank=True)
    total_value_text = models.CharField(max_length=255, blank=True)
    financing_text = models.CharField(max_length=255, blank=True)

    # 5. Formulário de captura (apresentação — campos do form em si são fixos)
    lead_form_heading = models.CharField(
        max_length=255,
        blank=True,
        default="Receba informações de consultores especializados",
    )
    lead_form_description = models.CharField(max_length=500, blank=True)
    lead_form_button_text = models.CharField(
        max_length=100, blank=True, default="Obter informações"
    )
    lead_form_button_color = models.CharField(max_length=20, blank=True, default="#2563eb")

    # 6. Vídeo institucional
    video_section_title = models.CharField(max_length=255, blank=True)
    video_embed_url = models.URLField(blank=True)

    # 7. Requisitos
    requirements_title = models.CharField(max_length=255, blank=True, default="Requisitos")
    requirements_rich_text = models.TextField(blank=True)

    # 8. Características do imóvel
    features_title = models.CharField(
        max_length=255, blank=True, default="Características do Imóvel"
    )
    features_rich_text = models.TextField(blank=True)
    features_image = models.ImageField(
        upload_to="landing_pages/features/", blank=True, null=True
    )

    # 9. Orçamento/oportunidade
    budget_rich_text = models.TextField(blank=True)

    # 10. CTA final + rodapé
    final_cta_text = models.CharField(max_length=100, blank=True)
    footer_text = models.CharField(max_length=255, blank=True)

    # Tracking (por landing page, não por tenant/domínio — PRD §7.4)
    facebook_pixel_id = models.CharField(max_length=50, blank=True)
    google_ads_id = models.CharField(max_length=50, blank=True)

    # Auditoria (PRD §8)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="unique_slug_per_tenant")
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def _unique_slug(self, base_slug):
        slug = base_slug
        suffix = 1
        qs = LandingPage.objects.filter(tenant=self.tenant)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        while qs.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        return slug

    def save(self, *args, **kwargs):
        if self.pk:
            # Slug is locked forever once the page has been published at
            # least once — publicly shared links must never break.
            previous = LandingPage.objects.filter(pk=self.pk).values_list(
                "slug", "published_at"
            ).first()
            if previous and previous[1] is not None:
                self.slug = previous[0]
        if not self.slug:
            self.slug = self._unique_slug(slugify(self.title) or "landing-page")
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.status == self.PUBLISHED


class LandingPageGalleryImage(models.Model):
    landing_page = models.ForeignKey(
        LandingPage, on_delete=models.CASCADE, related_name="gallery_images"
    )
    image = models.ImageField(upload_to="landing_pages/gallery/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.landing_page.title} — imagem {self.order}"


class LandingPageAuditLog(models.Model):
    CREATED = "created"
    UPDATED = "updated"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ACTION_CHOICES = [
        (CREATED, "Criada"),
        (UPDATED, "Atualizada"),
        (PUBLISHED, "Publicada"),
        (UNPUBLISHED, "Despublicada"),
    ]

    landing_page = models.ForeignKey(
        LandingPage, on_delete=models.CASCADE, related_name="audit_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.landing_page.title}: {self.get_action_display()} em {self.timestamp:%Y-%m-%d %H:%M}"
