from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import TenantDashboardMixin

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
