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
