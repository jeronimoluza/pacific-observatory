"""
Spider for Dirk (Netherlands) — https://www.dirk.nl/.

Nuxt/Vue SSR discounter storefront. Full product catalog is enumerable via
`/products-sitemap.xml` (7,384 `/boodschappen/.../<slug>/<id>` URLs live,
2026-09-06), so this walks the sitemap rather than crawling categories.

Each PDP is server-rendered with a `schema.org/Product` JSON-LD block in
`<head>`. Note the site's own JSON-LD uses a non-standard capitalised
`"Price"` key on the Offer object (not the usual lowercase `price`) — both
are checked. Sample verified live: "Broccoli" (mpn 4431) EUR 2.30,
category from the URL path segment before the slug ("groente").
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.dirk.nl/products-sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
MAX_PRODUCTS = 10000  # safety cap, above the ~7.4k observed catalog size


def _find_products(node):
    """Recursively find dicts with @type == "Product" in a JSON-LD @graph."""
    found = []
    if isinstance(node, dict):
        if node.get("@type") == "Product":
            found.append(node)
        for v in node.values():
            found.extend(_find_products(v))
    elif isinstance(node, list):
        for v in node:
            found.extend(_find_products(v))
    return found


class DirkNlSpider(scrapy.Spider):
    name = "dirk_nl"
    allowed_domains = ["dirk.nl"]
    currency = "EUR"
    language = "nl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        logger.info("dirk_nl: sitemap lists %d product URLs", len(locs))
        for url in locs[:MAX_PRODUCTS]:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LD_JSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (ValueError, TypeError):
                continue
            products = _find_products(data)
            if products:
                product = products[0]
                break

        if not product:
            logger.warning("dirk_nl: no Product JSON-LD on %s", response.url)
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price") or offers.get("Price")
        name = product.get("name")
        if not name or price in (None, "", 0):
            return

        # Category: the path segment just before the product slug/id, e.g.
        # /boodschappen/aardappelen-groente-fruit/groente/broccoli/4431 -> "groente"
        parts = [p for p in response.url.split("/") if p]
        category = parts[-3] if len(parts) >= 4 else None

        yield {
            "product_id": product.get("mpn") or product.get("sku") or response.url,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in (offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
