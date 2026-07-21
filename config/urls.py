from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from landingpages.views import public_page

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("landingpages.urls")),
    path("dashboard/leads/", include("leads.urls")),
    path("", TemplateView.as_view(template_name="base.html"), name="home"),
    # Path-based fallback for tenants without a verified custom domain:
    # meusaas.com/<tenant_slug>/<page_slug>/
    path("<slug:tenant_slug>/<slug:page_slug>/", public_page, name="public_page"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
