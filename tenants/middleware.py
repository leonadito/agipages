from .models import Tenant


class TenantResolutionMiddleware:
    """Resolves the tenant for the current request from the Host header.

    - If the Host matches a verified tenant custom domain, `request.tenant`
      is set to that Tenant and `request.urlconf` is swapped to the
      custom-domain urlconf, which only exposes the public landing-page
      route (never the dashboard/admin) — a second, structural layer of
      tenant isolation on top of the view-level checks.
    - Otherwise `request.tenant` is None and the platform urlconf handles
      the path-based fallback (`/<tenant_slug>/<page_slug>/`), resolving
      the tenant inside the view itself.

    The admin dashboard must NEVER use `request.tenant` (or any URL segment)
    to scope data — it always derives tenant from `request.user.tenant`.
    This middleware exists only to make the public site work on both a
    verified custom domain and the platform fallback domain.
    """

    CUSTOM_DOMAIN_URLCONF = "config.urls_custom_domain"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0]
        request.tenant = (
            Tenant.objects.filter(custom_domain=host, domain_verified=True).first()
        )
        if request.tenant is not None:
            request.urlconf = self.CUSTOM_DOMAIN_URLCONF
        return self.get_response(request)
