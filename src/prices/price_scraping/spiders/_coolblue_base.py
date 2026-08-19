"""
Shared base class for Coolblue storefront spiders (coolblue.nl, coolblue.be).

Custom Next.js-flavoured storefront, not one of the four platform bases.
Category "filter" pages (<BASE_URL>/<CATEGORY_PREFIX><cat>/filter) are
server-rendered with a fixed ~22-product page — there is no server-side
pagination link, further pages are loaded client-side via JS the site
blocks headless/curl access to (confirmed: a bare Playwright chromium
context gets served a stub "Coolblue - alles voor een glimlach" page), so
this scopes to CATEGORIES x the first server-rendered page each rather than
a full catalog walk. Each product detail page embeds a clean schema.org
Product JSON-LD block (name/sku/offers.price/offers.priceCurrency/
availability) — the listing pages are used only to discover PDP urls, which
are always rendered as absolute <BASE_URL>/... hrefs on both tenants.

The site rate-limits bursty requests (403s observed site-wide after ~15
rapid unthrottled requests from one IP) — keep DOWNLOAD_DELAY conservative.

Subclasses set: name, allowed_domains, currency, language, BASE_URL (scheme
+ host, no trailing slash), CATEGORY_PREFIX (e.g. "" for coolblue.nl, "nl/"
for coolblue.be).

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

CATEGORIES = [
    "laptops",
    "mobiele-telefoons/smartphones",
    "tablets",
    "televisies",
    "monitoren",
    "koelkasten",
    "wasmachines",
    "wasdrogers",
    "vaatwassers",
    "ovens",
    "magnetrons",
    "airfryers",
    "koffiezetapparaten",
    "keukenmachines",
    "stofzuigers",
    "robotstofzuigers",
    "aircos",
    "smartwatches",
    "oordopjes",
    "printers",
    "desktops",
    "cameras",
    "drones",
    "beamers",
]

_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>', re.DOTALL
)
_HREF_RE = re.compile(
    r'href="(https://www\.coolblue\.\w+/(?:[a-z]{2}/)?product/\d+/[a-z0-9-]+\.html)"'
)


class CoolblueBaseSpider(scrapy.Spider):
    name = None
    BASE_URL: str = ""
    CATEGORY_PREFIX: str = ""

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for cat in CATEGORIES:
            url = f"{self.BASE_URL}/{self.CATEGORY_PREFIX}{cat}/filter"
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": cat},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        hrefs = sorted(
            {h for h in _HREF_RE.findall(response.text) if h.startswith(self.BASE_URL)}
        )
        logger.info(f"{self.name}: category={category} product_links={len(hrefs)}")
        for href in hrefs:
            yield scrapy.Request(
                href,
                callback=self.parse_pdp,
                errback=self.errback,
                meta={"category": category},
            )

    def parse_pdp(self, response):
        category = response.meta["category"]
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break
        if not product:
            return

        name = product.get("name")
        offers = product.get("offers") or {}
        price = offers.get("price")
        if not name or price in (None, "", 0):
            return

        yield {
            "product_id": str(product.get("sku") or ""),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(offers.get("availability", "")).endswith("InStock"),
            "url": product.get("url") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Live scrape
    # (parse_pdp, above) already reads this exact page type -- Coolblue PDPs
    # are the same JSON-LD-bearing surface whether fetched live or replayed
    # from an archive, so this is a thin wrapper over the shared
    # archived-page tier rather than a reimplementation. Measured on 16
    # archived pages across both tenants (coolblue.nl, coolblue.be): 16/16
    # hit the shared JSON-LD tier -- no bespoke DOM walk was needed.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Coolblue product-detail page.

        Pure/stateless: no Scrapy Response, no network, no class state.
        Yields 0 or more rows; yields nothing when the page isn't a product
        page. Does NOT stamp `scraped_at_utc` -- the backfiller stamps the
        snapshot time itself.
        """
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        for row in rows:
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row
