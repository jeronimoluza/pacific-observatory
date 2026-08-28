"""
Spider for goods2door.com — Turks and Caicos Islands.

Wix Stores grocery-delivery site ("online grocery delivery service for
guests traveling to the Turks & Caicos Islands"). No open JSON API (Wix
Stores catalog is client-rendered), but the site publishes a Wix-generated
sitemap index at /sitemap.xml -> store-products-sitemap.xml listing 1,511
product-page URLs. Each PDP embeds a schema.org Product JSON-LD block
server-side, confirmed live 2026-08-18: 'Gerber Pure Water' -> USD 4.25,
InStock. Note the block uses non-standard capitalized keys ("Offers" /
"Availability" instead of "offers" / "availability") — Wix's own template
quirk, not a parsing bug; the parser below checks both cases.

No breadcrumb JSON-LD or inline breadcrumb DOM found on the PDP — category
left null rather than invented. product_id is the URL slug (stable, no
numeric SKU exposed).
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.goods2door.com/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
    re.DOTALL,
)


class Goods2DoorTcSpider(scrapy.Spider):
    name = "goods2door_tc"
    allowed_domains = ["goods2door.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        for loc in _LOC_RE.findall(response.text):
            if "store-products-sitemap" in loc:
                yield scrapy.Request(loc, callback=self.parse_product_sitemap)

    def parse_product_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info("goods2door_tc: %d product URLs in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break

        if not product:
            return

        offers = product.get("offers") or product.get("Offers") or {}
        price = offers.get("price") or offers.get("lowPrice")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        availability = offers.get("availability") or offers.get("Availability") or ""

        yield {
            "product_id": unquote(response.url.rstrip("/").rsplit("/", 1)[-1]),
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(availability).endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
