"""
Cassandra Online Market (Haiti) -- https://www.cassandraonlinemarket.com/.

Standard WooCommerce Store API. Site tagline is "Online Grocery and More for
Haiti and abroad!" -- customers order online and pick up at one of four
physical grocery stores on the ground in Haiti (see /ordering-pickup/), so
this is a real Haiti retailer, not a pure drop-ship catalog. Prices are
denominated in USD as returned by the Store API (currency_code=USD,
currency_minor_unit=2) -- NOT HTG, and NOT converted here. This is a
diaspora-facing pricing convention (order from abroad, pick up in-country),
confirmed live 2026-09-01.

A small minority of listings (~1.2% of a 500-row sample) are explicitly
priced for direct shipment to the US/Canada instead of Haiti pickup -- e.g.
"Alacta Plus Milk 1650 g X 6 (US / CANADA)" at $570 vs the Haiti-pickup
variant "... (Haiti Only)" at $300 for what is otherwise the same product.
The WooCommerce `international` category tag is NOT a reliable filter for
this (it appears on both variants), so we filter on the US/Canada-shipment
name suffix instead and drop those rows to avoid mixing the two price
tiers under one product line.
"""

import re

from price_scraping.spiders._woo_base import WooBaseSpider

_US_CANADA_VARIANT = re.compile(
    r"(u\.?s\.?a?\.?\s*[/&]\s*canada|usa\s*bulk|\(us\)|\(canada\)|us/canada|shipping to us)",
    re.I,
)


class CassandraonlinemarketHtSpider(WooBaseSpider):
    name = "cassandraonlinemarket_ht"
    allowed_domains = ["cassandraonlinemarket.com", "www.cassandraonlinemarket.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://www.cassandraonlinemarket.com/wp-json/wc/store/v1/products"

    # The repo-wide pinned curl_cffi profile (settings.py IMPERSONATE_BROWSERS,
    # chrome120) gets a 403 from this tenant's WAF; chrome124/123/safari17_0 all
    # clear it (confirmed live 2026-09-01). Disable the random-profile
    # middleware just for this spider and pin chrome124 via _woo_base's
    # IMPERSONATE_PROFILE hook.
    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        # Match the User-Agent header to the chrome124 TLS fingerprint below --
        # curl_cffi forwards Scrapy's own headers verbatim, so leaving the
        # inherited chrome120 UA string here would send a mismatched
        # TLS-vs-header fingerprint (chrome124 handshake, chrome120 UA),
        # which is itself enough to draw the 403.
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    IMPERSONATE_PROFILE = "chrome124"

    def _item(self, p: dict):
        name = str(p.get("name") or "")
        if _US_CANADA_VARIANT.search(name):
            return None
        return super()._item(p)
