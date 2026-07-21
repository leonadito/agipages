from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from landingpages.models import LandingPage, LandingPageAuditLog, LandingPageGalleryImage
from tenants.models import Tenant

ASSETS_DIR = settings.BASE_DIR / "diamond-infinity-towers"
GALLERY_DIR = ASSETS_DIR / "diamond-infinity-towers_imagens-empreendimento"

DEMO_TENANT_SLUG = "diamond-infinity-towers"
DEMO_USER_EMAIL = "demo@diamondtowers.com.br"
DEMO_USER_PASSWORD = "DiamondDemo123"


class Command(BaseCommand):
    help = (
        "Cria/atualiza um tenant e uma landing page de demonstração publicada, "
        "usando o conteúdo real da pasta diamond-infinity-towers/ como seed."
    )

    def handle(self, *args, **options):
        if not GALLERY_DIR.exists():
            self.stderr.write(
                self.style.ERROR(f"Pasta de imagens não encontrada: {GALLERY_DIR}")
            )
            return

        tenant, tenant_created = Tenant.objects.get_or_create(
            slug=DEMO_TENANT_SLUG, defaults={"name": "Diamond Infinity Towers"}
        )

        user, user_created = User.objects.get_or_create(
            email=DEMO_USER_EMAIL, defaults={"tenant": tenant}
        )
        if user_created:
            user.set_password(DEMO_USER_PASSWORD)
            user.tenant = tenant
            user.save()
        elif user.tenant_id != tenant.id:
            user.tenant = tenant
            user.save()

        gallery_files = sorted(
            GALLERY_DIR.glob("*.jpeg"),
            key=lambda p: int("".join(filter(str.isdigit, p.stem)) or 0),
        )
        hero_image_path = gallery_files[0]
        features_image_path = gallery_files[1] if len(gallery_files) > 1 else gallery_files[0]

        landing_page, page_created = LandingPage.objects.get_or_create(
            tenant=tenant,
            title="Diamond Infinity Towers",
            defaults={"created_by": user, "updated_by": user},
        )

        landing_page.hero_subtitle = (
            "O novo marco da orla — apartamentos de alto padrão com vista para o mar."
        )
        landing_page.hero_title = "Diamond Infinity Towers"
        landing_page.hero_cta_text = "Receba informações exclusivas"
        landing_page.hero_cta_target = "lead-form"
        landing_page.highlight_bar_text = (
            "Condições exclusivas para corretores da convenção — Tabela Zero."
        )
        # Transcrito de diamond-infinity-condicoes-pagamento.jpeg (exemplo
        # "Apto. 1 dorm."); não há campo de imagem/PDF modelado para
        # condições financeiras, então os valores viram texto (ver plano,
        # Marco 4, ambiguidade #10).
        landing_page.down_payment_text = "Entrada de 10% — a partir de R$ 55.000,00"
        landing_page.installment_text = (
            "Saldo em 100x a partir de R$ 3.850,00 + 8 reforços anuais de R$ 13.750,00"
        )
        landing_page.total_value_text = "Condições exclusivas para corretores da convenção"
        landing_page.financing_text = (
            "Campanha válida por até 60 dias. Valores sujeitos a reajuste pelo INCC."
        )
        landing_page.lead_form_heading = "Receba informações de consultores especializados"
        landing_page.lead_form_description = (
            "Preencha o formulário abaixo para mais informações de aprovações de "
            "financiamento, simulações e detalhes dos imóveis."
        )
        landing_page.lead_form_button_text = "Obter informações"
        landing_page.requirements_title = "Requisitos"
        landing_page.requirements_rich_text = (
            "Simples: nossa missão é tornar sua jornada simples e descomplicada.\n"
            "- Sem restrição no SPC e Serasa\n"
            "- Comprovação de renda facilitada"
        )
        landing_page.features_title = "Características do Imóvel"
        landing_page.features_rich_text = (
            "Imóveis de alto padrão, com opções de loft, apartamento de 1 dormitório "
            "e sala comercial. Acabamento de primeira linha e localização privilegiada."
        )
        landing_page.budget_rich_text = (
            "Com entrada facilitada e parcelas que cabem no seu bolso, o Diamond "
            "Infinity Towers torna-se uma oportunidade imperdível. Garanta já a sua unidade."
        )
        landing_page.final_cta_text = "Receba informações exclusivas"
        landing_page.footer_text = "Diamond Infinity Towers"
        landing_page.updated_by = user

        with open(hero_image_path, "rb") as f:
            landing_page.hero_background_image.save(hero_image_path.name, File(f), save=False)
        with open(features_image_path, "rb") as f:
            landing_page.features_image.save(features_image_path.name, File(f), save=False)

        landing_page.save()

        if not landing_page.gallery_images.exists():
            for order, image_path in enumerate(gallery_files):
                with open(image_path, "rb") as f:
                    gallery_image = LandingPageGalleryImage(
                        landing_page=landing_page, order=order
                    )
                    gallery_image.image.save(image_path.name, File(f), save=False)
                    gallery_image.save()

        if not landing_page.is_published:
            landing_page.status = LandingPage.PUBLISHED
            landing_page.published_by = user
            landing_page.published_at = timezone.now()
            landing_page.save()

        LandingPageAuditLog.objects.get_or_create(
            landing_page=landing_page,
            action=LandingPageAuditLog.CREATED if page_created else LandingPageAuditLog.UPDATED,
            user=user,
        )

        public_url = f"/{tenant.slug}/{landing_page.slug}/"
        self.stdout.write(self.style.SUCCESS("Seed concluído."))
        self.stdout.write(f"Tenant: {tenant.name} (slug={tenant.slug})")
        self.stdout.write(f"Usuário demo: {DEMO_USER_EMAIL} / senha: {DEMO_USER_PASSWORD}")
        self.stdout.write(f"Landing page publicada em: {public_url}")
