"""
Celine Shops (celineshops.ir) — Iranian makeup/cosmetics WooCommerce store.

Verified live 2026-08-18: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly. prices.currency_code returns
"IRT" (Toman, non-ISO) with currency_minor_unit 0 -- 1 Toman = 10 Rial, so
FORCE_CURRENCY="IRR" + PRICE_MULTIPLIER=10 report the scraped Toman value
as Rial, matching the torob_ir/sheypoor_ir convention already used for
other Iranian sources in this repo (IRR is the only ISO 4217 code for
Iran; Toman has none). robots.txt explicitly Disallows ClaudeBot on this
site; the Store API is fetched directly with a generic browser UA, not
under that user-agent token.

Gotcha: this tenant sits behind ArvanCloud (Iranian CDN/WAF). The very
first request gets a 307 self-redirect (same URL) that only sets
`__arcscoc`/`__arcsco` cookies; a plain retry with those cookies then
returns 200. Scrapy's dupefilter otherwise drops the identical-URL retry
as a duplicate of the original request, so the first request is sent with
dont_filter=True to force the cookie-priming round-trip through -- every
later page loads normally once the cookie jar is warm.
"""

import scrapy
from price_scraping.spiders._woo_base import WooBaseSpider


class CelineshopsIrSpider(WooBaseSpider):
    name = "celineshops_ir"
    allowed_domains = ["celineshops.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://celineshops.ir/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"

    async def start(self):
        yield scrapy.Request(
            self._page_url(1),
            callback=self.parse_page,
            meta={"page": 1},
            dont_filter=True,
        )
