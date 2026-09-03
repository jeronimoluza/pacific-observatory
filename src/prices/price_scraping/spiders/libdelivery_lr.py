"""LIBdelivery (Liberia) — WooCommerce marketplace, Store API not exposed.

Groceries, local products and restaurant plates under /item/. Liberia is a
dual-currency economy; the PDP JSON-LD states USD, which the base keeps.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class LibdeliveryLrSpider(WooSitemapBaseSpider):
    name = "libdelivery_lr"
    allowed_domains = ["libdelivery.com", "www.libdelivery.com"]
    # /sitemap.xml 301s here; requesting the final URL directly keeps the
    # pinned TLS profile off the redirect path.
    SITEMAP_URL = "https://libdelivery.com/sitemap_index.xml"
    PRODUCT_URL_RE = r"/item/"
    currency = "USD"
    language = "en"

    # The repo-pinned chrome120 profile 403s on this tenant's Cloudflare edge;
    # chrome124 / chrome123 / safari17_0 all return 200 (probed 2026-09-01).
    # Pinning the profile takes all three of these together: disable the random
    # browser middleware (it overwrites meta["impersonate"] per request), set
    # the matching User-Agent (curl_cffi forwards Scrapy's headers verbatim, so
    # a chrome124 handshake under a chrome120 UA draws the 403 by itself), and
    # set IMPERSONATE_PROFILE for the handler.
    custom_settings = {
        **WooSitemapBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    IMPERSONATE_PROFILE = "chrome124"
