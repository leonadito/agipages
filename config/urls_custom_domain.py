"""URLconf used for requests arriving on a verified tenant custom domain.

Deliberately minimal: only the public landing-page route belongs here.
The dashboard, accounts, and Django admin must never be reachable through
a tenant's custom domain — only through the platform domain — so they are
intentionally absent from this urlconf. The actual public-page route is
added in Milestone 4.
"""

urlpatterns = []
