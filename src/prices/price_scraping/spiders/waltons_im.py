"""
Waltons Direct (Isle of Man) -- https://waltons.im/.

TV and electrical retailer on WooCommerce. Store API v1 returns GBP with
currency_minor_unit=2. The tenant's WAF 403s the repo-wide chrome120 profile
and clears safari17_0 (probed 2026-10-05), so the random-profile middleware
is disabled and safari17_0 is pinned through IMPERSONATE_PROFILE.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class WaltonsImSpider(WooBaseSpider):
    name = "waltons_im"
    allowed_domains = ["waltons.im"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://waltons.im/wp-json/wc/store/v1/products"
    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ),
    }
