"""URLconf used for requests arriving on a verified tenant custom domain.

Deliberately minimal: only the public landing-page route belongs here.
The dashboard, accounts, and Django admin must never be reachable through
a tenant's custom domain — only through the platform domain.
"""
from django.urls import path

from landingpages.views import public_page

urlpatterns = [
    path("<slug:page_slug>/", public_page, name="public_page_domain"),
    # A landing page titled exactly "/" gets an empty slug (see
    # LandingPage.save()) and is served at the bare domain root.
    path("", public_page, name="public_page_domain_root"),
]
