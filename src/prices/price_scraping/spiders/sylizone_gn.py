"""Syli Zone -- https://www.sylizone.com/ (Conakry, Guinea).

Football-jersey ("maillot") reseller. Next.js App Router site; the homepage
and category-ish pages (``/boutique``) are RSC-streamed and not worth
parsing directly, but each product detail page embeds a clean
``application/ld+json`` ``Product`` node with a nested ``Offer``
(``priceCurrency: "GNF"``, plain-integer ``price``) -- confirmed
server-rendered under plain curl_cffi, no Playwright needed. og:title on
each PDP explicitly says "... en Guinée" confirming locality.

The catalog is tiny and enumerated once from ``/sitemap.xml``, which lists
exactly the ``/produit/<id>`` PDP URLs (ids 13-24, 12 products total as of
2026-09-11) alongside non-product pages (``/boutique``, ``/services/<id>``,
``/blog/<slug>``, ``/a-propos``, ``/contact``) that this spider filters out.
There is no separate category/listing API to page through -- the sitemap
itself is the enumeration surface (Phase 3's "product-sitemap.xml -> PDP ->
JSON-LD" fallback path).

Probed 2026-09-11 (untried_1 batch; batch row tagged this
"ALREADY-TRACKED-UPSTREAM" per Will's handover, but no matching manifest was
found in this repo, so it was probed fresh). Spider parses: PDP (sitemap for
enumeration, JSON-LD for extraction).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.sylizone.com/sitemap.xml"
_PRODUCT_RE = re.compile(r"^https://www\.sylizone\.com/produit/\d+$")


class SylizoneGnSpider(scrapy.Spider):
    name = "sylizone_gn"
    allowed_domains = ["sylizone.com"]
    currency = "GNF"
    language = "fr"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_URL, callback=self.parse_sitemap, errback=self.errback,
        )

    def parse_sitemap(self, response):
        locs = re.findall(r"<loc>(.*?)</loc>", response.text)
        product_urls = [u for u in locs if _PRODUCT_RE.match(u)]
        logger.info(
            "%s: %d sitemap urls, %d product urls", self.name, len(locs), len(product_urls)
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        m = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', response.text, re.S
        )
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return
        if data.get("@type") != "Product":
            return

        name = (data.get("name") or "").strip()
        offer = data.get("offers") or {}
        price = offer.get("price")
        currency = offer.get("priceCurrency") or self.currency
        if not name or price in (None, 0):
            return
        try:
            amount = float(price)
        except (TypeError, ValueError):
            return
        if amount <= 0:
            return

        yield {
            "product_id": response.url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": name,
            "category": None,
            "price": f"{amount:.2f}",
            "currency": currency,
            "available": "InStock" in (offer.get("availability") or ""),
            "url": offer.get("url") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            "%s: request failed %s — %r", self.name, failure.request.url, failure.value
        )
