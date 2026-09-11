"""
Tingo (Greenland) -- https://tingo.gl/.

Nuuk fashion/apparel WooCommerce storefront. Standard public Store API at
/wp-json/wc/store/v1/products; DKK prices at currency_minor_unit=2 (e.g.
raw "150000" -> kr. 1500.00). 238 products across 3 pages (X-WP-Total:
238, X-WP-TotalPages: 3 as of 2026-09-11), confirmed disjoint ids page 1
vs page 2 (page 1 starts at product 65820 "Camilla coat", page 2 includes
product 62227 "Nujigga suede skirt" -- distinct ids, both non-zero DKK).

Gotcha: same "Simply.com" host + CleanTalk-style firewall (`ct_sfw_pass_key`
cookie) as inuitquality.com, in the same Greenland source batch --
intermittently returns a non-standard HTTP 454 with zero JSON body under
back-to-back requests from one IP. A 3-page crawl issuing pages 1/2/3
in sequence is exactly the kind of back-to-back pattern that can trip it
mid-crawl (observed live: page 1 succeeded, page 2 454'd, crawl stopped
short at 100/238 items because the old `generic_woo_configured` config had
no 454 in its retry list). RETRY_HTTP_CODES below adds 454 so
RetryMiddleware retries it like any other transient block.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TingoGlSpider(WooBaseSpider):
    name = "tingo_gl"
    allowed_domains = ["tingo.gl"]
    currency = "DKK"
    language = "da"
    BASE_URL = "https://tingo.gl/wp-json/wc/store/v1/products"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 454],
        # A bare 2.0s DOWNLOAD_DELAY between the page-1 request and a
        # page-2 retry was not enough gap to clear the firewall's
        # short-lived block (observed live: 3 retries at ~2-3s spacing
        # all still 454'd). 6.0s + more retries gives the block time to
        # lapse; this is a 3-page catalog so the extra wall time is small.
        "DOWNLOAD_DELAY": 6.0,
        "RETRY_TIMES": 5,
    }
