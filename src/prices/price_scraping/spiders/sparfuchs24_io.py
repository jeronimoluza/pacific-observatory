"""
Spider for Sparfuchs24 (Germany) — https://sparfuchs24.io/.

WordPress/WooCommerce deals-aggregator ("Preisvergleich & Top Angebote" --
price comparison / top deals). Every product is WooCommerce `type: external`
(an affiliate link out to the actual seller, e.g. Amazon) -- prices are the
deal price captured by the site at listing time, not a first-party retail
price. Tagged `channel: marketplace` for that reason (matches the
"third-party sellers, seller/price not authored by the outlet" test), which
already excludes it from enrich/census.py's corpus census.

curl_cffi (chrome124/120/116) 403s on every request including /sitemap.xml
-- but a real headless Chromium clears the challenge on first navigation with
no CAPTCHA (confirmed live 2026-08-18: plain Playwright goto to `/` ->
200). scrapy-playwright's default browser context is shared across requests
in one spider run, so a warmup request to `/` earns the Cloudflare clearance
cookie the subsequent Store API requests need.

Navigating Playwright directly to the JSON API URL wraps the body in Chrome's
built-in JSON viewer (`<html>...<body><pre>{escaped JSON}</pre></body></html>`,
with `&` further HTML-escaped to `&amp;`), so the page text needs one
html.unescape() pass before json.loads() -- confirmed live: this recovers the
identical payload plain `requests` gets from the Store API when unblocked.
Product parsing reuses WooBaseSpider._item (minor-unit price division,
html.unescape on names).

Each product's `description` field runs ~1.5MB (bloated SEO copy) -- the
base class's per_page=100 blows up to ~150MB/page and the Playwright
navigation times out at 60s rendering that into the JSON viewer. Confirmed
live: per_page=10 (~15MB) loads in ~10s, so this spider overrides the page
size instead of using WooBaseSpider's PER_PAGE=100.

Sample confirmed: "OOONO Co-Driver NO2 [NEUES Modell 2025]..." EUR 56.00.
"""

import html
import json
import logging
import re

import scrapy

from price_scraping.spiders._woo_base import WooBaseSpider

logger = logging.getLogger(__name__)

_PRE_RE = re.compile(r"<pre[^>]*>(.*)</pre>", re.S)
_GOTO_KWARGS = {"wait_until": "domcontentloaded"}
_PAGE_SIZE = 10
_MAX_PAGES = 200


class Sparfuchs24IoSpider(WooBaseSpider):
    name = "sparfuchs24_io"
    allowed_domains = ["sparfuchs24.io"]
    currency = "EUR"
    language = "de"
    BASE_URL = "https://sparfuchs24.io/wp-json/wc/store/v1/products"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
    }

    def _page_url(self, page: int) -> str:
        return f"{self.BASE_URL}?per_page={_PAGE_SIZE}&page={page}"

    async def start(self):
        yield scrapy.Request(
            "https://sparfuchs24.io/",
            callback=self.parse_warmup,
            errback=self.errback,
            meta={"playwright": True, "playwright_page_goto_kwargs": _GOTO_KWARGS},
        )

    def parse_warmup(self, response):
        yield scrapy.Request(
            self._page_url(1),
            callback=self.parse_page,
            errback=self.errback,
            meta={
                "page": 1,
                "playwright": True,
                "playwright_page_goto_kwargs": _GOTO_KWARGS,
            },
        )

    def parse_page(self, response):
        m = _PRE_RE.search(response.text)
        raw = html.unescape(m.group(1)) if m else response.text
        try:
            products = json.loads(raw)
        except ValueError:
            logger.warning(f"non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info(f"sparfuchs24_io page={page} count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= _PAGE_SIZE and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._page_url(nxt),
                callback=self.parse_page,
                errback=self.errback,
                meta={
                    "page": nxt,
                    "playwright": True,
                    "playwright_page_goto_kwargs": _GOTO_KWARGS,
                },
            )

    def errback(self, failure):
        logger.error(
            f"sparfuchs24_io request failed: {failure.request.url} — {failure.value!r}"
        )
