from unittest import mock

from django.test import RequestFactory, TestCase, override_settings

from djangocms_multisite import middleware
from djangocms_multisite.middleware import CMSMultiSiteMiddleware


@override_settings(
    ROOT_URLCONF="tests.test_utils.urls_site_a",
    MULTISITE_CMS_URLS={
        "a.example.com": "tests.test_utils.urls_site_a",
        "b.example.com": "tests.test_utils.urls_site_b",
    },
    MULTISITE_CMS_ALIASES={},
    MULTISITE_CMS_FALLBACK="",
    MIDDLEWARE=["djangocms_multisite.middleware.CMSMultiSiteMiddleware"],
)
class CMSMultiSiteSecurityTest(TestCase):
    def setUp(self):
        middleware._cms_urls_key = None

    def test_request_is_routed_with_host_urlconf(self):
        """A route only defined in site A's urlconf is not reachable through site B's host."""
        self.assertEqual(self.client.get("/internal-only/", HTTP_HOST="a.example.com").status_code, 200)
        self.assertEqual(self.client.get("/internal-only/", HTTP_HOST="b.example.com").status_code, 404)
        self.assertEqual(self.client.get("/public/", HTTP_HOST="b.example.com").status_code, 200)

    def test_urlconf_is_not_reloaded_on_every_request(self):
        with mock.patch.object(middleware, "reload_urlconf") as reload_urlconf:
            for _ in range(10):
                self.client.get("/public/", HTTP_HOST="b.example.com")
        self.assertEqual(reload_urlconf.call_count, 1)

    def test_urlconf_is_reloaded_when_site_changes(self):
        with mock.patch.object(middleware, "reload_urlconf") as reload_urlconf:
            with self.settings(SITE_ID=1):
                self.client.get("/public/", HTTP_HOST="b.example.com")
                self.client.get("/public/", HTTP_HOST="b.example.com")
            with self.settings(SITE_ID=2):
                self.client.get("/public/", HTTP_HOST="b.example.com")
        self.assertEqual(reload_urlconf.call_count, 2)

    def test_ipv6_host(self):
        with self.settings(MULTISITE_CMS_URLS={"::1": "tests.test_utils.urls_site_b"}):
            request = RequestFactory().get("/", HTTP_HOST="[::1]:8000")
            self.assertEqual(CMSMultiSiteMiddleware._get_domain(request), "::1")
