"""SPASE (Botswana) -- https://spasebw.com/.

Outdoor / travel-goods retailer: luggage (Cellini), knives (Muela), torches
(Nextorch), camping gear. WooCommerce with an OPEN Store API, 144 products
(X-WP-Total=144), currency_code BWP, currency_minor_unit 2.

WAF GOTCHA -- same tenant-level defense as pretty_potions_bw and the reason
this is not generic_woo_configured: every Chrome and Safari curl_cffi profile
(chrome120, chrome124, chrome131, safari17_0) returns a 6,192-byte 403 stub
even on the bare homepage, and only `firefox133` clears it. All three parts of
the override are required together -- disable RandomBrowserMiddleware, pin
IMPERSONATE_PROFILE, and match USER_AGENT to the same Firefox build.

Verified: "Qwest Medium Trolley Case" BWP 1899.95 (raw 189995 minor units).
Page family: API.
"""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class SpasebwSpider(WooBaseSpider):
    name = "spasebw"
    allowed_domains = ["spasebw.com"]
    BASE_URL = "https://spasebw.com/wp-json/wc/store/v1/products"
    currency = "BWP"
    language = "en"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
    }
    IMPERSONATE_PROFILE = "firefox133"
