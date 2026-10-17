"""Uploaded images in Cloudflare R2 (decision of 2026-10-16).

The bucket is private and agitare.com.br is not on Cloudflare yet, so the
app delivers the images itself: the storage writes to R2 (folder R2_PREFIX)
but builds URLs on our own /media/ path, and `media_file` streams the image
from R2 with a long browser cache. The page HTML does not change. When the
domain moves to Cloudflare, a public bucket with its own address can take
over the delivery.
"""
import mimetypes
import re

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe
from storages.backends.s3 import S3Storage

# Only the landing pages' images: the beta key also reaches other apps'
# folders of the bucket, which must never be served from here.
SERVABLE = re.compile(r"^landing_pages/[\w./-]+$")
CACHE_SECONDS = 7 * 24 * 3600  # uploads never overwrite a name, so a long cache is safe


class R2MediaStorage(S3Storage):
    def url(self, name, parameters=None, expire=None, http_method=None):
        return f"/{settings.MEDIA_URL.lstrip('/')}{name}"


@require_safe
def media_file(request, path):
    if not SERVABLE.match(path) or ".." in path:
        raise Http404
    try:
        # R2 opens lazily (an error would only show mid-response): ask first.
        if not default_storage.exists(path):
            raise Http404
        handle = default_storage.open(path, "rb")
    except SuspiciousFileOperation:
        raise Http404
    response = FileResponse(handle, content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")
    response["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    response["X-Content-Type-Options"] = "nosniff"
    return response
