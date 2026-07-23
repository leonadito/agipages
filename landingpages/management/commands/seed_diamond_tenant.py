from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from landingpages.models import (
    LandingPage,
    LandingPageAmenity,
    LandingPageAuditLog,
    LandingPageGalleryImage,
)
from tenants.models import Tenant

ASSETS_DIR = settings.BASE_DIR / "diamond-infinity-towers"
GALLERY_DIR = ASSETS_DIR / "diamond-infinity-towers_imagens-empreendimento"

DEMO_TENANT_SLUG = "diamond-infinity-towers"
DEMO_USER_EMAIL = "demo@diamondtowers.com.br"
DEMO_USER_PASSWORD = "DiamondDemo123"

# Amenidades transcritas de folder-infinity-OF.pdf (seção "Infinitas
# possibilidades de lazer"). Não há campo modelado para uma lista livre de
# amenidades no template padrão — só a variante premium usa isso.
PREMIUM_AMENITIES = [
    ("Boulevard", "Ampla área de convivência inspirada na arquitetura wellness."),
    ("Hotel", "Hotel integrado para receber clientes, visitantes e encontros corporativos."),
    ("Lounge Business", "Espaço para reuniões e networking sem sair do empreendimento."),
    ("Restaurante", "Perfeito para almoços de negócios e momentos de descontração."),
    ("Academia", "Estrutura completa para treinar no seu ritmo, sem perder tempo."),
    ("Espaço Beauty", "Espaço dedicado à beleza, com conveniência e conforto."),
    ("Piscina", "Ambiente perfeito para relaxar e se divertir com quem você ama."),
    ("Espaço Kids", "Área interativa que desperta a imaginação e promove o convívio infantil."),
    ("Espaço Pet", "Estrutura para recreação e bem-estar do seu pet com total comodidade."),
    ("Quadra Padel", "Estrutura para a prática de um dos esportes que mais crescem."),
    ("Espaço Gourmet", "Ambiente planejado para reunir amigos e família."),
    ("Summit Space", "Salão de festas com infraestrutura imponente e design sofisticado."),
]


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

        premium_page = self._seed_premium_page(tenant, user, gallery_files)
        premium_url = f"/{tenant.slug}/{premium_page.slug}/"
        self.stdout.write(f"Landing page premium publicada em: {premium_url}")

    def _find_image(self, gallery_files, number):
        return next(p for p in gallery_files if p.stem.endswith(f"_{number}"))

    def _seed_premium_page(self, tenant, user, gallery_files):
        """Segunda landing page do tenant demo: mesmo formulário de captura,
        design autoral (não segue landing-page-exemplo.png), com o conteúdo
        completo do folder-infinity-OF.pdf (complexo multiuso — torre
        comercial, torre residencial e hotel)."""
        landing_page, page_created = LandingPage.objects.get_or_create(
            tenant=tenant,
            title="Diamond Infinity Towers — Lifestyle Completo",
            defaults={"created_by": user, "updated_by": user},
        )

        landing_page.design_variant = LandingPage.PREMIUM
        landing_page.hero_eyebrow = "A vida em alto padrão"
        landing_page.hero_title = "Diamond Infinity Towers"
        landing_page.hero_subtitle = (
            "O tempo a seu favor: moradia, negócios, lazer e hotelaria integrados "
            "em um único endereço, no coração do Vale do Taquari."
        )
        landing_page.hero_cta_text = "Quero conhecer o Infinity"
        landing_page.hero_cta_target = "lead-form"
        landing_page.highlight_bar_text = (
            "Torre Comercial · Torre Residencial · Hotel — tudo em um só lugar"
        )
        landing_page.down_payment_text = "Entrada de 10%"
        landing_page.installment_text = "Saldo em 100x + 8 reforços anuais"
        landing_page.total_value_text = "Condições exclusivas para corretores da convenção"
        landing_page.financing_text = (
            "Campanha válida por até 60 dias. Valores sujeitos a reajuste pelo INCC."
        )
        landing_page.location_title = "O Padrão Diamond de Viver Bem no Coração do Vale"
        landing_page.location_rich_text = (
            "Lajeado é referência em qualidade de vida. No bairro Americano, a região "
            "mais valorizada da cidade, o Diamond Infinity Towers une localização "
            "privilegiada, conforto e fácil acesso a serviços e escolas de excelência.\n\n"
            "Com acesso facilitado à BR-386, o empreendimento conecta você rapidamente "
            "aos principais eixos do estado, garantindo que você esteja no centro de "
            "tudo, mantendo a exclusividade de um endereço premium."
        )
        landing_page.lead_form_heading = "Fale com um consultor Diamond"
        landing_page.lead_form_description = (
            "Preencha seus dados e receba a tabela de preços, plantas e condições "
            "exclusivas da convenção."
        )
        landing_page.lead_form_button_text = "Quero minha proposta"
        landing_page.lead_form_button_color = "#0f766e"
        landing_page.features_title = "Duas Torres, Infinitas Possibilidades"
        landing_page.features_rich_text = (
            "Torre Comercial: 217 lojas e salas comerciais, de 35m² a 516m², com "
            "restaurante, lounge business e estacionamento rotativo amplo.\n\n"
            "Torre Residencial: 197 unidades, de studios a partir de 27m² a "
            "coberturas duplex de até 93m², com lazer completo no 5º pavimento."
        )
        landing_page.budget_rich_text = (
            "Com entrada de 10% e saldo em 100 parcelas, o Diamond Infinity Towers "
            "cabe no seu planejamento. Condições exclusivas por tempo limitado — "
            "garanta a sua unidade com atendimento personalizado."
        )
        landing_page.final_cta_text = "Quero receber a tabela de preços"
        landing_page.footer_text = "Diamond Infinity Towers — Construtora Diamond · Lajeado/RS"
        landing_page.updated_by = user

        hero_image_path = self._find_image(gallery_files, 14)
        features_image_path = self._find_image(gallery_files, 1)
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

        if not landing_page.amenities.exists():
            for order, (title, description) in enumerate(PREMIUM_AMENITIES):
                LandingPageAmenity.objects.create(
                    landing_page=landing_page,
                    title=title,
                    description=description,
                    order=order,
                )

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
        return landing_page
