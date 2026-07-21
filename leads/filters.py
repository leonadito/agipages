import django_filters

from landingpages.models import LandingPage

from .models import Lead


class LeadFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte", label="De"
    )
    date_to = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte", label="Até"
    )
    utm_source = django_filters.CharFilter(lookup_expr="icontains", label="Origem (UTM)")

    class Meta:
        model = Lead
        fields = ["landing_page", "status", "utm_source", "date_from", "date_to"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Scoped to the tenant so the filter dropdown (and any crafted
        # landing_page= query param) can never expose another tenant's pages.
        self.filters["landing_page"].queryset = LandingPage.objects.filter(tenant=tenant)
