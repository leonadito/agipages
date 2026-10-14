from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.static import serve

from landingpages.views import public_page
from leads.integrity import integrity
from telegram_integration.urls import webhook_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    # Read-only answers for metaleads' nightly orphan check.
    path("api/v1/integrity/", integrity, name="integrity"),
    path("accounts/", include("accounts.urls")),
    # Single sign-on callback and start (only when OIDC_ENABLED, see below).
    path("dashboard/", include("landingpages.urls")),
    path("dashboard/leads/", include("leads.urls")),
    path("dashboard/telegram/", include("telegram_integration.urls")),
    path("dashboard/domain/", include("tenants.urls")),
    path("dashboard/conversoes-meta/", include("meta_conversions.urls")),
    # Public endpoint Telegram's servers call directly — not behind login.
    path("telegram/", include((webhook_urlpatterns, "telegram_webhook"))),
    path("", TemplateView.as_view(template_name="base.html"), name="home"),
    # Path-based fallback for tenants without a verified custom domain:
    # meusaas.com/<tenant_slug>/<page_slug>/
    path("<slug:tenant_slug>/<slug:page_slug>/", public_page, name="public_page"),
    # A landing page titled exactly "/" gets an empty slug (see
    # LandingPage.save()) and is meant to act as that tenant's homepage —
    # this is the closest equivalent to "domain root" available on the
    # shared fallback domain, since the real root ("") above is already
    # the platform's own page.
    path("<slug:tenant_slug>/", public_page, name="public_page_tenant_root"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    # static() is a no-op without DEBUG, so wire the view directly, ahead of
    # the catch-all public page routes.
    urlpatterns.insert(
        0, re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})
    )

if settings.OIDC_ENABLED:
    # /oidc/authenticate/ (start) and /oidc/callback/ (return from the core).
    # Inserted at the top: the catch-all public page routes would match first.
    urlpatterns.insert(0, path("oidc/", include("mozilla_django_oidc.urls")))
    # Single logout: the core POSTs a logout_token here (accounts/backchannel.py).
    from accounts.backchannel import backchannel_logout

    urlpatterns.insert(0, path("oidc/backchannel-logout/", backchannel_logout, name="oidc_backchannel_logout"))
