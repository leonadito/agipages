from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.utils.text import slugify


def split_email_list(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def validate_email_list(value):
    for address in split_email_list(value):
        try:
            validate_email(address)
        except ValidationError:
            raise ValidationError(f"'{address}' não é um e-mail válido.")


class LandingPage(models.Model):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [
        (DRAFT, "Rascunho"),
        (PUBLISHED, "Publicada"),
    ]

    STANDARD = "standard"
    PREMIUM = "premium"
    CUSTOM = "custom"
    DESIGN_VARIANT_CHOICES = [
        (STANDARD, "Padrão"),
        (PREMIUM, "Premium (design autoral, alto padrão)"),
        (CUSTOM, "HTML personalizado (avançado)"),
    ]

    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="landing_pages"
    )
    title = models.CharField("Título da landing page (interno)", max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    is_homepage = models.BooleanField(
        "Página inicial (raiz do domínio)",
        default=False,
        help_text=(
            "Em vez de viver em /pagina/, esta página passa a responder na "
            "raiz do domínio (ex: seudominio.com/ em vez de "
            "seudominio.com/pagina/). Só uma página por tenant pode ser a "
            "inicial. Assim como o slug, só tem efeito enquanto a página "
            "ainda não foi publicada pela primeira vez — depois disso a URL "
            "fica travada."
        ),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    # Qual template público renderiza esta página. "premium" usa um layout
    # visual próprio (não segue o padrão de landing-page-exemplo.png), mas
    # continua alimentado pelos mesmos campos estruturados e pelo mesmo
    # formulário de captura de lead.
    design_variant = models.CharField(
        "Variante de design",
        max_length=20,
        choices=DESIGN_VARIANT_CHOICES,
        default=STANDARD,
    )
    # Usado só pela variante "custom": HTML completo da página, fornecido
    # pelo tenant, renderizado sem alterações (mesmo modelo de confiança de
    # financial_conditions_html — só o dono autenticado do tenant escreve
    # aqui). A substituição dos tokens {{LEAD_FORM}}/{{TRACKING_SCRIPTS}} é
    # feita com str.replace() literal em landingpages/views.py::public_page,
    # nunca pelo motor de templates do Django — rodar conteúdo de tenant
    # através do Template Engine abriria Server-Side Template Injection.
    custom_html = models.TextField(
        "HTML personalizado da página (avançado)", blank=True
    )

    # 1. Hero
    hero_background_image = models.ImageField(
        "Imagem de fundo do hero", upload_to="landing_pages/hero/", blank=True, null=True
    )
    hero_background_video_url = models.URLField(
        "URL de vídeo de fundo (opcional)", blank=True
    )
    hero_eyebrow = models.CharField(
        "Texto de apoio acima do título", max_length=100, blank=True
    )
    hero_title = models.CharField("Título principal (H1)", max_length=255, blank=True)
    hero_subtitle = models.CharField("Subtítulo", max_length=500, blank=True)
    hero_cta_text = models.CharField(
        "Texto do botão de ação (CTA)",
        max_length=100,
        blank=True,
        default="Receba informações exclusivas",
    )
    hero_cta_target = models.CharField(
        "Âncora de destino do botão (ex: lead-form)",
        max_length=100,
        blank=True,
        default="lead-form",
    )

    # 2. Faixa de destaque
    highlight_bar_text = models.CharField(
        "Texto da faixa de destaque", max_length=500, blank=True
    )

    # 4. Condições financeiras
    down_payment_text = models.CharField("Valor de entrada", max_length=255, blank=True)
    installment_text = models.CharField("Valor da parcela", max_length=255, blank=True)
    total_value_text = models.CharField("Valor total", max_length=255, blank=True)
    financing_text = models.CharField(
        "Texto sobre financiamento", max_length=255, blank=True
    )
    # Conteúdo livre em HTML puro para esta seção (ex: tabela de valores
    # customizada) — renderizado sem escapar no template público, então só
    # o próprio dono do tenant (autenticado) pode preenchê-lo.
    financial_conditions_html = models.TextField(
        "Conteúdo HTML personalizado (opcional)", blank=True
    )

    # 5. Formulário de captura (apresentação + configuração dos campos)
    lead_form_heading = models.CharField(
        "Título do formulário",
        max_length=255,
        blank=True,
        default="Receba informações de consultores especializados",
    )
    lead_form_description = models.CharField(
        "Texto de apoio do formulário", max_length=500, blank=True
    )
    lead_form_button_text = models.CharField(
        "Texto do botão de envio",
        max_length=100,
        blank=True,
        default="Obter informações",
    )
    lead_form_button_color = models.CharField(
        "Cor do botão de envio", max_length=20, blank=True, default="#2563eb"
    )
    # Nome e cidade são sempre fixos e obrigatórios; e-mail e telefone podem
    # ser desligados/tornados opcionais por página (ex: cliente que só quer
    # WhatsApp, sem e-mail). Campos extras ficam em LandingPageFormField.
    show_email = models.BooleanField("Exibir campo de e-mail", default=True)
    require_email = models.BooleanField("E-mail obrigatório", default=True)
    show_phone = models.BooleanField(
        "Exibir campo de telefone/WhatsApp", default=True
    )
    require_phone = models.BooleanField(
        "Telefone/WhatsApp obrigatório", default=True
    )
    phone_label = models.CharField(
        "Rótulo do campo de telefone",
        max_length=50,
        blank=True,
        default="Telefone",
    )
    # Opcional: além de salvar o Lead normalmente (dashboard/Telegram/Meta
    # Conversions), redireciona o visitante para o WhatsApp logo após o
    # envio bem-sucedido — fluxo comum em landing pages de corretores que
    # já usam WhatsApp como canal principal de atendimento.
    whatsapp_redirect_number = models.CharField(
        "Número do WhatsApp para redirecionamento (DDI+DDD+número, só dígitos)",
        max_length=20,
        blank=True,
    )
    whatsapp_redirect_message = models.CharField(
        "Mensagem pré-preenchida do WhatsApp",
        max_length=500,
        blank=True,
        help_text="O primeiro nome do lead é adicionado automaticamente ao final.",
    )
    # Opcional: além de salvar o Lead normalmente, avisa por e-mail a cada
    # envio (ver email_notifications/) — para quem migrou de um site que
    # mandava o formulário por e-mail e quer continuar recebendo assim.
    lead_notification_emails = models.CharField(
        "E-mails que recebem aviso de novo lead",
        max_length=500,
        blank=True,
        validators=[validate_email_list],
        help_text="Um ou mais e-mails, separados por vírgula. Deixe em branco para não enviar.",
    )

    # Opcional: além de salvar o Lead normalmente, espelha cada envio para
    # um Google Forms já existente do tenant (ex: para manter uma planilha
    # de respostas que ele já usava antes de migrar para esta plataforma).
    # O ID vem da própria URL de envio do formulário do Google
    # (".../forms/d/e/<ID>/formResponse"); cada google_form_entry_* mapeia
    # um campo fixo daqui para o "entry.NNNNNNN" correspondente no Google
    # Forms (visível inspecionando o HTML do formulário do Google). Campos
    # extras (LandingPageFormField) têm seu próprio mapeamento individual.
    google_form_id = models.CharField(
        "ID do Google Forms para espelhar as respostas (opcional)",
        max_length=100,
        blank=True,
        help_text="O trecho entre /forms/d/e/ e /formResponse na URL de envio do formulário do Google.",
    )
    google_form_entry_name = models.CharField(
        "Campo do Google Forms para o Nome", max_length=50, blank=True
    )
    google_form_entry_phone = models.CharField(
        "Campo do Google Forms para o Telefone", max_length=50, blank=True
    )
    google_form_entry_email = models.CharField(
        "Campo do Google Forms para o E-mail", max_length=50, blank=True
    )
    google_form_entry_city = models.CharField(
        "Campo do Google Forms para a Cidade", max_length=50, blank=True
    )

    # 6. Vídeo institucional
    video_section_title = models.CharField(
        "Título da seção de vídeo", max_length=255, blank=True
    )
    video_embed_url = models.URLField(
        "URL de incorporação do vídeo (YouTube/Vimeo embed)", blank=True
    )

    # 7. Requisitos
    requirements_title = models.CharField(
        "Título da seção de requisitos",
        max_length=255,
        blank=True,
        default="Requisitos",
    )
    requirements_rich_text = models.TextField("Texto de requisitos", blank=True)

    # 8. Características do imóvel
    features_title = models.CharField(
        "Título das características",
        max_length=255,
        blank=True,
        default="Características do Imóvel",
    )
    features_rich_text = models.TextField("Texto de características", blank=True)
    features_image = models.ImageField(
        "Imagem de características",
        upload_to="landing_pages/features/",
        blank=True,
        null=True,
    )

    # 9. Orçamento/oportunidade
    budget_rich_text = models.TextField("Texto de orçamento/oportunidade", blank=True)

    # Localização — usado pela variante "premium" (não faz parte das 10
    # seções fixas do template padrão).
    location_title = models.CharField(
        "Título da seção de localização", max_length=255, blank=True
    )
    location_rich_text = models.TextField("Texto sobre localização", blank=True)

    # 10. CTA final + rodapé
    final_cta_text = models.CharField("Texto do botão final", max_length=100, blank=True)
    footer_text = models.CharField("Texto do rodapé", max_length=255, blank=True)

    # Tracking (por landing page, não por tenant/domínio — PRD §7.4)
    facebook_pixel_id = models.CharField(
        "ID do Facebook Pixel", max_length=50, blank=True
    )
    google_ads_id = models.CharField(
        "ID de conversão do Google Ads", max_length=50, blank=True
    )

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
        slug_locked = False
        if self.pk:
            # Slug is locked forever once the page has been published at
            # least once — publicly shared links must never break.
            previous = LandingPage.objects.filter(pk=self.pk).values_list(
                "slug", "published_at"
            ).first()
            if previous and previous[1] is not None:
                self.slug = previous[0]
                slug_locked = True
        if not slug_locked:
            if self.is_homepage:
                # An empty slug is what makes the <tenant_slug>/ and
                # custom-domain root URLs resolve to this page (see
                # public_page's page_slug="" default). Checked on every
                # unlocked save (not just "if blank") so toggling the
                # checkbox on an existing page takes effect. The
                # (tenant, slug) unique constraint stops a second homepage
                # per tenant outright; LandingPageFormViewMixin.form_valid
                # checks for that first to surface a friendly error instead.
                self.slug = ""
            elif not self.slug:
                self.slug = self._unique_slug(slugify(self.title) or "landing-page")
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.status == self.PUBLISHED


class LandingPageGalleryImage(models.Model):
    landing_page = models.ForeignKey(
        LandingPage, on_delete=models.CASCADE, related_name="gallery_images"
    )
    image = models.ImageField("Imagem", upload_to="landing_pages/gallery/")
    caption = models.CharField("Legenda", max_length=255, blank=True)
    order = models.PositiveIntegerField("Ordem", default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.landing_page.title} — imagem {self.order}"


class LandingPageAmenity(models.Model):
    """Lista livre de amenidades/diferenciais (ex: Boulevard, Spa, Academia),
    usada pela variante "premium" para empreendimentos com muitos espaços
    além das 10 seções fixas do template padrão."""

    landing_page = models.ForeignKey(
        LandingPage, on_delete=models.CASCADE, related_name="amenities"
    )
    title = models.CharField("Título", max_length=120)
    description = models.CharField("Descrição", max_length=255, blank=True)
    order = models.PositiveIntegerField("Ordem", default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.landing_page.title} — {self.title}"


class LandingPageFormField(models.Model):
    """Campos extras e configuráveis do formulário de captura, além dos
    campos fixos nome/cidade e dos campos opcionais e-mail/telefone
    (controlados pelas flags show_/require_ em LandingPage). Renderizados
    dinamicamente por leads.forms.build_lead_capture_form; as respostas são
    salvas em Lead.extra_field_values (JSONField), chaveadas por field_key."""

    TEXT = "text"
    PHONE = "phone"
    EMAIL = "email"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    TEXTAREA = "textarea"
    FIELD_TYPE_CHOICES = [
        (TEXT, "Texto curto"),
        (PHONE, "Telefone"),
        (EMAIL, "E-mail"),
        (SELECT, "Seleção (dropdown)"),
        (RADIO, "Escolha única (radio)"),
        (CHECKBOX, "Caixa de marcação"),
        (TEXTAREA, "Texto longo"),
    ]

    landing_page = models.ForeignKey(
        LandingPage, on_delete=models.CASCADE, related_name="form_fields"
    )
    field_key = models.SlugField(
        "Identificador do campo",
        max_length=60,
        help_text="Usado como chave nas respostas salvas. Ex: interesse, timeline-decisao.",
    )
    label = models.CharField("Rótulo exibido", max_length=150)
    field_type = models.CharField(
        "Tipo de campo", max_length=20, choices=FIELD_TYPE_CHOICES, default=TEXT
    )
    required = models.BooleanField("Obrigatório", default=False)
    options_text = models.TextField(
        "Opções (uma por linha)",
        blank=True,
        help_text="Usado apenas para Seleção/Escolha única.",
    )
    order = models.PositiveIntegerField("Ordem", default=0)
    google_form_entry_id = models.CharField(
        "Campo correspondente no Google Forms (entry.NNNNNNN)",
        max_length=50,
        blank=True,
        help_text="Deixe em branco se este campo não deve ser espelhado no Google Forms.",
    )

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["landing_page", "field_key"],
                name="unique_field_key_per_page",
            )
        ]

    def __str__(self):
        return f"{self.landing_page.title} — {self.label}"

    def options(self):
        return [line.strip() for line in self.options_text.splitlines() if line.strip()]


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
