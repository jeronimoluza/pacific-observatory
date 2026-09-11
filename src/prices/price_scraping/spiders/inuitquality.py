"""
Inuit Quality (Greenland) -- https://inuitquality.com/.

Small Nuuk clothing/accessories WooCommerce storefront. Standard public
Store API at /wp-json/wc/store/v1/products; DKK prices at
currency_minor_unit=2 (e.g. raw "34900" -> kr. 349.00), confirmed against
the site's own price_html on the same row. 73 products total (single
page, X-WP-Total: 73 as of 2026-09-11).

Gotcha: this tenant (behind a "Simply.com" host + CleanTalk-style firewall
-- note the `ct_sfw_pass_key` cookie it sets) intermittently returns a
non-standard HTTP 454 with zero JSON body instead of the real page under
back-to-back/bursty requests from one IP; a single isolated request always
got 200 in testing, and re-requesting after a short cooldown also
recovers. This is what produced a "clean 0-row" run before this fix -- the
manifest's earlier `generic_woo_configured` config had no 454 in its
retry list, so a single 454 killed the whole crawl. RETRY_HTTP_CODES
below adds 454 so RetryMiddleware retries it like any other transient
block.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class InuitqualitySpider(WooBaseSpider):
    name = "inuitquality"
    allowed_domains = ["inuitquality.com"]
    currency = "DKK"
    language = "da"
    BASE_URL = "https://inuitquality.com/wp-json/wc/store/v1/products"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 454],
    }
