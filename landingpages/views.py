from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView
from django_ratelimit.decorators import ratelimit

from core.mixins import TenantDashboardMixin
from leads.forms import LeadCaptureForm
from tenants.models import Tenant

from .forms import GalleryImageFormSet, LandingPageForm, get_publish_errors
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
        (5, "Formulário de captura"),
        (6, "Vídeo institucional"),
        (7, "Requisitos"),
        (8, "Características"),
        (9, "Orçamento"),
        (10, "CTA final + rodapé"),
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
        else:
            context["gallery_formset"] = GalleryImageFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        gallery_formset = context["gallery_formset"]
        if not gallery_formset.is_valid():
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
        form = LeadCaptureForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.tenant = tenant
            lead.landing_page = landing_page
            for key in UTM_PARAMS:
                setattr(lead, key, request.POST.get(key, ""))
            lead.ip_address = request.META.get("REMOTE_ADDR")
            lead.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
            lead.save()
            return render(
                request,
                "public/partials/lead_form_success.html",
                {"landing_page": landing_page},
            )
        return render(
            request,
            "public/partials/lead_form.html",
            {"landing_page": landing_page, "form": form, "tracking": tracking},
            status=400,
        )

    form = LeadCaptureForm()
    return render(
        request,
        "public/landing_page.html",
        {
            "landing_page": landing_page,
            "tenant": tenant,
            "form": form,
            "tracking": tracking,
        },
    )
