import threading
from urllib.parse import urlsplit

from cms.utils.apphook_reload import get_local_revision, reload_urlconf
from django.conf import settings
from django.urls import set_urlconf
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin

# cms.urls embeds the apphook patterns of the site that was current when it was
# (re)loaded, so it is process-wide state: track which site it was built for and
# only rebuild it when that changes, one thread at a time.
_cms_urls_lock = threading.Lock()
_cms_urls_key = None


def _current_site_id():
    try:
        return int(settings.SITE_ID)
    except (AttributeError, TypeError, ValueError):
        # SITE_ID unset, or a multisite SiteID with neither a current site nor a default
        return None


def _ensure_cms_urls_for_current_site():
    global _cms_urls_key
    key = (_current_site_id(), get_local_revision())
    if _cms_urls_key == key:
        return
    with _cms_urls_lock:
        if _cms_urls_key != key:
            reload_urlconf()
            _cms_urls_key = key


class CMSMultiSiteMiddleware(MiddlewareMixin):
    @staticmethod
    def _get_sites():
        return getattr(settings, "MULTISITE_CMS_URLS", {})

    @staticmethod
    def _get_aliases():
        return getattr(settings, "MULTISITE_CMS_ALIASES", {})

    @classmethod
    def _get_domain(cls, request):
        """
        Check current request domain against configured domains and alias
        """
        sites = cls._get_sites()
        aliases = cls._get_aliases()
        # get_host() validates against ALLOWED_HOSTS; hostname strips the port,
        # lowercases and handles bracketed IPv6 literals.
        host = urlsplit("//" + request.get_host()).hostname
        if not host:
            return None
        if host in sites:
            return host
        for domain, hosts in aliases.items():
            if host in hosts:
                return domain
        return None

    @classmethod
    def _get_urlconf(cls, domain):
        """
        Return the urlconf for the given domain in configuration.

        If given does not match, fallback is checked.

        If domain is ``None`` or no matching urlconf if found, ``None`` is returned,
        resulting in setting the default urlconf.
        """
        sites = cls._get_sites()
        MULTISITE_CMS_FALLBACK = getattr(settings, "MULTISITE_CMS_FALLBACK", "")  # noqa
        try:
            urlconf = sites[domain]
        except KeyError:
            urlconf = None
        if not urlconf and MULTISITE_CMS_FALLBACK and MULTISITE_CMS_FALLBACK in sites.keys():
            urlconf = sites[MULTISITE_CMS_FALLBACK]
        return urlconf

    def process_request(self, request):
        domain = self._get_domain(request)
        urlconf = self._get_urlconf(domain)
        if urlconf:
            # Django resolves the request with request.urlconf; the thread-local
            # urlconf alone only affects reverse(), so without this every host
            # would be routed through ROOT_URLCONF.
            request.urlconf = urlconf
        # sets urlconf for current thread, so that code that does not know
        # about the request (e.g MyModel.get_absolute_url()) get the correct
        # urlconf.
        # urlconf might be None, in that case, the default is set
        set_urlconf(urlconf)
        _ensure_cms_urls_for_current_site()

    def process_response(self, request, response):
        patch_vary_headers(response, ("Host",))
        # set back to default urlconf
        set_urlconf(None)
        return response
