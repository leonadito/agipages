import csv

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import DetailView, ListView

from core.mixins import TenantDashboardMixin

from .filters import LeadFilter
from .models import Lead, LeadStatusHistory


class Echo:
    """A file-like object that just returns what it's given — lets
    csv.writer stream rows through StreamingHttpResponse without buffering
    the whole export in memory."""

    def write(self, value):
        return value


CSV_HEADER = [
    "Nome",
    "Email",
    "Telefone",
    "Cidade",
    "Landing Page",
    "Status",
    "UTM Source",
    "UTM Medium",
    "UTM Campaign",
    "Criado em",
]


def _lead_csv_row(lead):
    return [
        lead.name,
        lead.email,
        lead.phone,
        lead.city,
        lead.landing_page.title,
        lead.get_status_display(),
        lead.utm_source,
        lead.utm_medium,
        lead.utm_campaign,
        lead.created_at.strftime("%Y-%m-%d %H:%M"),
    ]


def _stream_csv_rows(leads):
    writer = csv.writer(Echo())
    yield writer.writerow(CSV_HEADER)
    for lead in leads:
        yield writer.writerow(_lead_csv_row(lead))


class LeadListView(TenantDashboardMixin, ListView):
    model = Lead
    template_name = "leads/list.html"
    context_object_name = "leads"
    paginate_by = 25

    def get_base_queryset(self):
        return Lead.objects.filter(tenant=self.tenant).select_related("landing_page")

    def get_queryset(self):
        self.filterset = LeadFilter(
            self.request.GET, queryset=self.get_base_queryset(), tenant=self.tenant
        )
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.filterset
        context["status_choices"] = Lead.STATUS_CHOICES
        return context


class LeadDetailView(TenantDashboardMixin, DetailView):
    model = Lead
    template_name = "leads/detail.html"
    context_object_name = "lead"

    def get_queryset(self):
        return Lead.objects.filter(tenant=self.tenant).select_related("landing_page")


class LeadStatusUpdateView(TenantDashboardMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, tenant=self.tenant)
        new_status = request.POST.get("status")
        valid_statuses = dict(Lead.STATUS_CHOICES)
        if new_status in valid_statuses and new_status != lead.status:
            old_status = lead.status
            lead.status = new_status
            lead.save(update_fields=["status", "updated_at"])
            LeadStatusHistory.objects.create(
                lead=lead,
                old_status=old_status,
                new_status=new_status,
                changed_by=request.user,
            )
        return render(
            request,
            "leads/partials/lead_row.html",
            {"lead": lead, "status_choices": Lead.STATUS_CHOICES},
        )


class LeadExportCSVView(TenantDashboardMixin, View):
    def get(self, request):
        base_queryset = Lead.objects.filter(tenant=self.tenant).select_related("landing_page")
        filterset = LeadFilter(request.GET, queryset=base_queryset, tenant=self.tenant)
        response = StreamingHttpResponse(
            _stream_csv_rows(filterset.qs), content_type="text/csv"
        )
        response["Content-Disposition"] = 'attachment; filename="leads.csv"'
        return response
