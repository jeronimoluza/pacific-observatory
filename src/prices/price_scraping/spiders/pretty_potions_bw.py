"""Pretty Potions (Botswana) -- https://www.prettypotions.shop/.

K-beauty / skincare retailer. WooCommerce with an OPEN Store API (90 products,
X-WP-Total=90, currency_code BWP, currency_minor_unit 2).

WAF GOTCHA -- this is why it does not use generic_woo_configured. The tenant
403s EVERY Chrome and Safari curl_cffi profile (chrome120, chrome124,
chrome131, safari17_0 all return a 6,192-byte 403 stub, including on the bare
homepage) and clears only on `firefox133`. The repo-wide pinned profile is
chrome120, and scrapy-impersonate's RandomBrowserMiddleware would overwrite
meta["impersonate"] on every request, so all three parts of the override are
required together: disable RandomBrowserMiddleware, pin IMPERSONATE_PROFILE,
and match USER_AGENT to the same Firefox build (curl_cffi forwards Scrapy's
headers verbatim, so a firefox133 handshake under a Chrome UA is its own 403
tell).

Verified: "Rice 70 Glow Milky Toner" BWP 300.00 (raw 30000 minor units).
Page family: API.
"""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class PrettyPotionsBwSpider(WooBaseSpider):
    name = "pretty_potions_bw"
    allowed_domains = ["prettypotions.shop"]
    BASE_URL = "https://www.prettypotions.shop/wp-json/wc/store/v1/products"
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
