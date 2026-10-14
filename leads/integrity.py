"""Read-only answers for the nightly orphan check, which runs in metaleads
(the hub: it holds the core's tenant copy and the leads that point at pages
here). Nothing is changed by this endpoint.

POST /api/v1/integrity/  (Authorization: Bearer <INTEGRITY_API_TOKEN>)
body: {"pages": ["<page uuid>", ...]}
answer:
- pages: {uuid: {"status", "tenant": core uuid or null}} for the uuids that
  exist (a missing uuid is a page that no longer exists);
- tenants: every tenant here with its core uuid (null = never linked);
- undelivered_leads: form leads that metaleads never confirmed after every
  retry, or still pending after a day.
"""
import hmac
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from landingpages.models import LandingPage
from tenants.models import Tenant

from .metaleads import MAX_ATTEMPTS
from .models import Lead

MAX_PAGES = 5000


def _authorized(request):
    expected = getattr(settings, "INTEGRITY_API_TOKEN", "")
    auth = request.headers.get("Authorization", "")
    return bool(expected) and auth.startswith("Bearer ") and hmac.compare_digest(auth[7:].strip(), expected)


@csrf_exempt
@require_POST
def integrity(request):
    if not _authorized(request):
        return JsonResponse({"error": "não autorizado"}, status=401)
    try:
        body = json.loads(request.body or b"{}")
        asked = [str(uuid.UUID(str(u))) for u in body.get("pages") or []][:MAX_PAGES]
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "pages precisa ser uma lista de UUIDs"}, status=400)

    pages = {
        str(p.uuid): {"status": p.status, "tenant": str(p.tenant.core_uuid) if p.tenant.core_uuid else None}
        for p in LandingPage.objects.filter(uuid__in=asked).select_related("tenant")
    }
    tenants = [
        {"slug": t.slug, "name": t.name, "core_uuid": str(t.core_uuid) if t.core_uuid else None}
        for t in Tenant.objects.order_by("slug")
    ]
    stale = timezone.now() - timedelta(days=1)
    undelivered = [
        {"uuid": str(lead.uuid), "tenant": lead.tenant.slug, "attempts": lead.metaleads_attempts,
         "error": lead.metaleads_error[:300], "created_at": lead.created_at.isoformat()}
        for lead in Lead.objects.filter(metaleads_sent_at__isnull=True, metaleads_attempts__gt=0)
        .select_related("tenant").order_by("created_at")
        if lead.metaleads_attempts >= MAX_ATTEMPTS or lead.created_at < stale
    ]
    return JsonResponse({"pages": pages, "tenants": tenants, "undelivered_leads": undelivered})
