"""URLconf used for requests arriving on a verified tenant custom domain.

Deliberately minimal: only the public landing-page route belongs here.
The dashboard, accounts, and Django admin must never be reachable through
a tenant's custom domain — only through the platform domain.
"""
from django.conf import settings
from django.urls import path, re_path

from core.media import media_file
from landingpages.views import public_page

urlpatterns = [
    path("<slug:page_slug>/", public_page, name="public_page_domain"),
    # A landing page titled exactly "/" gets an empty slug (see
    # LandingPage.save()) and is served at the bare domain root.
    path("", public_page, name="public_page_domain_root"),
]

if settings.R2_BUCKET:
    # The page's images (Cloudflare R2, delivered by the app): only the
    # landing pages' folder, see core.media.
    urlpatterns.insert(0, re_path(r"^media/(?P<path>.+)$", media_file, name="media_file_domain"))
