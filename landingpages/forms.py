from django import forms
from django.forms import inlineformset_factory

from .models import (
    LandingPage,
    LandingPageAmenity,
    LandingPageFormField,
    LandingPageGalleryImage,
)


class LandingPageForm(forms.ModelForm):
    class Meta:
        model = LandingPage
        exclude = [
            "tenant",
            "slug",
            "status",
            "created_by",
            "updated_by",
            "published_by",
            "published_at",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "requirements_rich_text": forms.Textarea(attrs={"rows": 5}),
            "features_rich_text": forms.Textarea(attrs={"rows": 5}),
            "budget_rich_text": forms.Textarea(attrs={"rows": 5}),
            "location_rich_text": forms.Textarea(attrs={"rows": 5}),
            "hero_subtitle": forms.Textarea(attrs={"rows": 2}),
            "lead_form_description": forms.Textarea(attrs={"rows": 2}),
            "financial_conditions_html": forms.Textarea(
                attrs={"rows": 6, "class": "font-mono text-sm"}
            ),
            "custom_html": forms.Textarea(
                attrs={"rows": 20, "class": "font-mono text-sm"}
            ),
            "design_variant": forms.Select(attrs={"x-model": "variant"}),
        }


GalleryImageFormSet = inlineformset_factory(
    LandingPage,
    LandingPageGalleryImage,
    fields=("image", "caption", "order"),
    extra=3,
    can_delete=True,
)

AmenityFormSet = inlineformset_factory(
    LandingPage,
    LandingPageAmenity,
    fields=("title", "description", "order"),
    extra=3,
    can_delete=True,
)

FormFieldFormSet = inlineformset_factory(
    LandingPage,
    LandingPageFormField,
    fields=(
        "field_key",
        "label",
        "field_type",
        "required",
        "options_text",
        "order",
        "google_form_entry_id",
    ),
    extra=3,
    can_delete=True,
)


# Fields required to publish (PRD §7.2: só publica com o mínimo de conteúdo
# preenchido). A landing page pode ficar salva como rascunho incompleta,
# mas não pode ir ao ar faltando isso.
REQUIRED_FIELDS_TO_PUBLISH = ["hero_title", "lead_form_heading"]


def get_publish_errors(landing_page):
    if landing_page.design_variant == LandingPage.CUSTOM:
        # Página custom não tem as seções estruturadas nem a galeria. Os
        # tokens {{LEAD_FORM}}/{{TRACKING_SCRIPTS}} não são obrigatórios:
        # algumas páginas custom capturam o lead por fora do formulário
        # da plataforma (ex: botões de WhatsApp direto no HTML), então
        # exigi-los aqui bloquearia uma publicação legítima.
        if not landing_page.custom_html:
            return ["O campo 'HTML personalizado' está vazio."]
        return []

    errors = []
    for field_name in REQUIRED_FIELDS_TO_PUBLISH:
        if not getattr(landing_page, field_name):
            label = LandingPage._meta.get_field(field_name).verbose_name
            errors.append(f"O campo obrigatório '{label}' está vazio.")
    if not landing_page.pk or not landing_page.gallery_images.exists():
        errors.append("Adicione pelo menos uma imagem na galeria antes de publicar.")
    has_contact_method = (landing_page.show_phone and landing_page.require_phone) or (
        landing_page.show_email and landing_page.require_email
    )
    if not has_contact_method:
        errors.append(
            "Habilite e torne obrigatório pelo menos um contato (telefone ou e-mail) "
            "antes de publicar."
        )
    return errors
