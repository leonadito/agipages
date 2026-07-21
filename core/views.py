from django.views.generic import TemplateView

from .mixins import TenantDashboardMixin


class DashboardHomeView(TenantDashboardMixin, TemplateView):
    """Temporary placeholder — replaced by the landing pages list as the
    post-login landing spot once Milestone 3 adds that view."""

    template_name = "core/dashboard.html"
