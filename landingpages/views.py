from urllib.parse import quote

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView
from django_ratelimit.decorators import ratelimit

from core.mixins import TenantDashboardMixin
from leads.forms import build_lead_capture_form, extra_field_name, extract_extra_field_values
from leads.models import Lead
from tenants.models import Tenant

from .forms import (
    AmenityFormSet,
    FormFieldFormSet,
    GalleryImageFormSet,
    LandingPageForm,
    get_publish_errors,
)
from .models import LandingPage, LandingPageAuditLog


class LandingPageListView(TenantDashboardMixin, ListView):
    model = LandingPage
    template_name = "landingpages/list.html"
    context_object_name = "landing_pages"

    def get_queryset(self):
        return LandingPage.objects.filter(tenant=self.tenant)


class LandingPageFormViewMixin:
    form_class = LandingPageForm
    template_name = "landingpages/form.html"

    SECTION_TABS = [
        (1, "Hero"),
        (2, "Faixa de destaque"),
        (3, "Galeria"),
        (4, "Condições financeiras"),
        (5, "Localização"),
        (6, "Formulário de captura"),
        (7, "Vídeo institucional"),
        (8, "Requisitos"),
        (9, "Características"),
        (10, "Amenidades"),
        (11, "Orçamento"),
        (12, "CTA final + rodapé"),
    ]

    def get_queryset(self):
        return LandingPage.objects.filter(tenant=self.tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section_tabs"] = self.SECTION_TABS
        if self.request.method == "POST":
            context["gallery_formset"] = GalleryImageFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
            context["amenity_formset"] = AmenityFormSet(
                self.request.POST, instance=self.object
            )
            context["form_field_formset"] = FormFieldFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["gallery_formset"] = GalleryImageFormSet(instance=self.object)
            context["amenity_formset"] = AmenityFormSet(instance=self.object)
            context["form_field_formset"] = FormFieldFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        gallery_formset = context["gallery_formset"]
        amenity_formset = context["amenity_formset"]
        form_field_formset = context["form_field_formset"]
        if (
            not gallery_formset.is_valid()
            or not amenity_formset.is_valid()
            or not form_field_formset.is_valid()
        ):
            return self.render_to_response(self.get_context_data(form=form))

        with transaction.atomic():
            is_new = self.object is None
            landing_page = form.save(commit=False)
            landing_page.tenant = self.tenant
            if is_new:
                landing_page.created_by = self.request.user
            landing_page.updated_by = self.request.user
            landing_page.save()
            self.object = landing_page

            gallery_formset.instance = landing_page
            gallery_formset.save()

            amenity_formset.instance = landing_page
            amenity_formset.save()

            form_field_formset.instance = landing_page
            form_field_formset.save()

            LandingPageAuditLog.objects.create(
                landing_page=landing_page,
                user=self.request.user,
                action=(
                    LandingPageAuditLog.CREATED if is_new else LandingPageAuditLog.UPDATED
                ),
            )

        messages.success(self.request, "Landing page salva como rascunho.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("landingpages:edit", kwargs={"pk": self.object.pk})


class LandingPageCreateView(LandingPageFormViewMixin, TenantDashboardMixin, CreateView):
    model = LandingPage


class LandingPageUpdateView(LandingPageFormViewMixin, TenantDashboardMixin, UpdateView):
    model = LandingPage


class LandingPagePublishView(TenantDashboardMixin, View):
    def post(self, request, pk):
        landing_page = get_object_or_404(LandingPage, pk=pk, tenant=self.tenant)
        errors = get_publish_errors(landing_page)
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("landingpages:edit", pk=landing_page.pk)

        landing_page.status = LandingPage.PUBLISHED
        landing_page.published_by = request.user
        landing_page.published_at = timezone.now()
        landing_page.save()
        LandingPageAuditLog.objects.create(
            landing_page=landing_page,
            user=request.user,
            action=LandingPageAuditLog.PUBLISHED,
        )
        messages.success(request, "Landing page publicada.")
        return redirect("landingpages:list")


class LandingPageUnpublishView(TenantDashboardMixin, View):
    def post(self, request, pk):
        landing_page = get_object_or_404(LandingPage, pk=pk, tenant=self.tenant)
        landing_page.status = LandingPage.DRAFT
        landing_page.save()
        LandingPageAuditLog.objects.create(
            landing_page=landing_page,
            user=request.user,
            action=LandingPageAuditLog.UNPUBLISHED,
        )
        messages.success(request, "Landing page despublicada.")
        return redirect("landingpages:list")


UTM_PARAMS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
]


def _resolve_public_tenant(request, tenant_slug):
    """The public site's tenant, resolved either from the verified custom
    domain (request.tenant, set by TenantResolutionMiddleware) or from the
    <tenant_slug> path segment on the platform fallback domain. This is the
    ONLY place a URL segment is allowed to resolve a tenant — the dashboard
    must never do this (see core.mixins.TenantDashboardMixin)."""
    if request.tenant is not None:
        return request.tenant
    return get_object_or_404(Tenant, slug=tenant_slug)


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def public_page(request, page_slug, tenant_slug=None):
    tenant = _resolve_public_tenant(request, tenant_slug)
    # Drafts are never publicly reachable, on either URL form.
    landing_page = get_object_or_404(
        LandingPage, tenant=tenant, slug=page_slug, status=LandingPage.PUBLISHED
    )

    tracking = {key: request.GET.get(key, "") for key in UTM_PARAMS}

    if request.method == "POST":
        form = build_lead_capture_form(landing_page, data=request.POST)
        if form.is_valid():
            lead = Lead(
                tenant=tenant,
                landing_page=landing_page,
                name=form.cleaned_data["name"],
                email=form.cleaned_data.get("email", ""),
                phone=form.cleaned_data.get("phone", ""),
                city=form.cleaned_data["city"],
                extra_field_values=extract_extra_field_values(landing_page, form.cleaned_data),
            )
            for key in UTM_PARAMS:
                setattr(lead, key, request.POST.get(key, ""))
            lead.ip_address = request.META.get("REMOTE_ADDR")
            lead.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
            lead.fbp = request.COOKIES.get("_fbp", "")
            lead.fbc = request.COOKIES.get("_fbc", "")
            lead.save()
            return render(
                request,
                "public/partials/lead_form_success.html",
                {
                    "landing_page": landing_page,
                    "lead": lead,
                    "whatsapp_url": _whatsapp_redirect_url(landing_page, lead),
                },
            )
        return render(
            request,
            "public/partials/lead_form.html",
            {
                "landing_page": landing_page,
                "form": form,
                "tracking": tracking,
                "extra_fields": _extra_fields(landing_page, form),
            },
            status=400,
        )

    form = build_lead_capture_form(landing_page)
    context = {
        "landing_page": landing_page,
        "tenant": tenant,
        "form": form,
        "tracking": tracking,
        "extra_fields": _extra_fields(landing_page, form),
    }

    if landing_page.design_variant == LandingPage.CUSTOM:
        return HttpResponse(_render_custom_page(request, landing_page, context))

    template_name = (
        "public/landing_page_premium.html"
        if landing_page.design_variant == LandingPage.PREMIUM
        else "public/landing_page.html"
    )
    return render(request, template_name, context)


def _render_custom_page(request, landing_page, context):
    """Injeta o formulário de captura e os scripts de tracking no HTML
    fornecido pelo tenant via substituição literal de string — NUNCA passar
    landing_page.custom_html pelo motor de templates do Django
    (Template(...).render()), pois isso permitiria que HTML de tenant usasse
    {% load %}/{{ settings... }} para ler configuração do servidor (Server-
    Side Template Injection). str.replace() em tokens fixos não executa
    nada, só troca texto."""
    lead_form_html = render_to_string("public/partials/lead_form.html", context, request=request)
    tracking_html = render_to_string(
        "public/partials/tracking_scripts.html", {"landing_page": landing_page}
    )
    html = landing_page.custom_html.replace("{{LEAD_FORM}}", lead_form_html)
    html = html.replace("{{TRACKING_SCRIPTS}}", tracking_html)
    return html


def _extra_fields(landing_page, form):
    """Pareia cada LandingPageFormField com seu BoundField no form dinâmico,
    para o template só iterar e renderizar, sem lógica de nomes de campo."""
    return [
        (form_field, form[extra_field_name(form_field.field_key)])
        for form_field in landing_page.form_fields.all()
    ]


def _whatsapp_redirect_url(landing_page, lead):
    """Monta a URL do wa.me para redirecionar o visitante logo após o envio
    bem-sucedido, quando a página tem um número configurado. O primeiro
    nome do lead é anexado à mensagem, como no fluxo que substitui."""
    if not landing_page.whatsapp_redirect_number:
        return ""
    first_name = lead.name.strip().split(" ")[0] if lead.name.strip() else ""
    message = landing_page.whatsapp_redirect_message or ""
    if first_name:
        message = f"{message} Meu nome é {first_name}.".strip()
    return f"https://wa.me/{landing_page.whatsapp_redirect_number}?text={quote(message)}"
