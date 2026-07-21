from django import forms
from django.forms import inlineformset_factory

from .models import LandingPage, LandingPageGalleryImage


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
            "hero_subtitle": forms.Textarea(attrs={"rows": 2}),
            "lead_form_description": forms.Textarea(attrs={"rows": 2}),
        }


GalleryImageFormSet = inlineformset_factory(
    LandingPage,
    LandingPageGalleryImage,
    fields=("image", "caption", "order"),
    extra=3,
    can_delete=True,
)


# Fields required to publish (PRD §7.2: só publica com o mínimo de conteúdo
# preenchido). A landing page pode ficar salva como rascunho incompleta,
# mas não pode ir ao ar faltando isso.
REQUIRED_FIELDS_TO_PUBLISH = ["hero_title", "lead_form_heading"]


def get_publish_errors(landing_page):
    errors = []
    for field_name in REQUIRED_FIELDS_TO_PUBLISH:
        if not getattr(landing_page, field_name):
            label = LandingPage._meta.get_field(field_name).verbose_name
            errors.append(f"O campo obrigatório '{label}' está vazio.")
    if not landing_page.pk or not landing_page.gallery_images.exists():
        errors.append("Adicione pelo menos uma imagem na galeria antes de publicar.")
    return errors
