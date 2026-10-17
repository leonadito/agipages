from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .middleware import TrustedProxyClientIPMiddleware


@override_settings(TRUSTED_PROXY_CIDRS=["172.16.0.0/12"])
class TrustedProxyClientIPMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.seen = {}

        def view(request):
            self.seen["ip"] = request.META["REMOTE_ADDR"]
            return HttpResponse()

        self.middleware = TrustedProxyClientIPMiddleware(view)

    def _ip_after(self, remote_addr, **headers):
        request = self.factory.get("/", REMOTE_ADDR=remote_addr, **headers)
        self.middleware(request)
        return self.seen["ip"]

    def test_real_ip_header_from_trusted_proxy_replaces_remote_addr(self):
        self.assertEqual(
            self._ip_after("172.20.0.1", HTTP_X_REAL_IP="179.98.148.47"), "179.98.148.47"
        )

    def test_ipv6_real_ip_is_accepted(self):
        self.assertEqual(
            self._ip_after("172.20.0.1", HTTP_X_REAL_IP="2804:14c::1"), "2804:14c::1"
        )

    def test_header_from_untrusted_address_is_ignored(self):
        # A client reaching the app without passing through the proxy must
        # not be able to choose its own IP.
        self.assertEqual(self._ip_after("8.8.8.8", HTTP_X_REAL_IP="6.6.6.6"), "8.8.8.8")

    def test_malformed_header_is_ignored(self):
        self.assertEqual(
            self._ip_after("172.20.0.1", HTTP_X_REAL_IP="not-an-ip"), "172.20.0.1"
        )

    def test_missing_header_keeps_remote_addr(self):
        self.assertEqual(self._ip_after("172.20.0.1"), "172.20.0.1")

    @override_settings(TRUSTED_PROXY_CIDRS=[])
    def test_no_trusted_proxies_means_header_is_never_used(self):
        self.assertEqual(
            self._ip_after("172.20.0.1", HTTP_X_REAL_IP="179.98.148.47"), "172.20.0.1"
        )


class MediaFileTests(SimpleTestCase):
    """Images in Cloudflare R2 delivered by the app (core.media)."""

    def setUp(self):
        import shutil
        import tempfile

        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        from unittest import mock

        from django.core.files.storage import FileSystemStorage

        patcher = mock.patch("core.media.default_storage", FileSystemStorage(location=self.media))
        patcher.start()
        self.addCleanup(patcher.stop)
        import os

        os.makedirs(os.path.join(self.media, "landing_pages", "hero"))
        with open(os.path.join(self.media, "landing_pages", "hero", "capa.png"), "wb") as f:
            f.write(b"\x89PNG-teste")
        os.makedirs(os.path.join(self.media, "outros"))
        with open(os.path.join(self.media, "outros", "segredo.txt"), "wb") as f:
            f.write(b"nao")

    def get(self, path):
        from .media import media_file

        return media_file(RequestFactory().get(f"/media/{path}"), path)

    def test_serves_landing_page_images_with_a_long_cache(self):
        r = self.get("landing_pages/hero/capa.png")
        self.assertEqual(b"".join(r.streaming_content), b"\x89PNG-teste")
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertEqual(r["Cache-Control"], "public, max-age=604800")
        r.close()

    def test_refuses_other_folders_traversal_and_missing_files(self):
        from django.http import Http404

        for path in ("outros/segredo.txt", "landing_pages/../outros/segredo.txt", "landing_pages/hero/nada.png",
                     "../core/perfis/x.png"):
            with self.assertRaises(Http404, msg=path):
                self.get(path)

    def test_r2_storage_builds_urls_on_our_own_media_path(self):
        from .media import R2MediaStorage

        storage = R2MediaStorage(bucket_name="b", endpoint_url="https://x.us.r2.cloudflarestorage.com", access_key="k",
                                 secret_key="s", region_name="auto", location="agipages", default_acl=None)
        self.assertEqual(storage.url("landing_pages/hero/capa.png"), "/media/landing_pages/hero/capa.png")
        self.assertEqual(storage._normalize_name("landing_pages/hero/capa.png"), "agipages/landing_pages/hero/capa.png")
