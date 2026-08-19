"""
Spider for MamaMe (Iraq) — www.mamame.iq, mother/baby-focused general retailer
(baby feeding/diapers/formula alongside broader womens/mens wear, electronics).
Next.js SSR (App Router). URL discovery via the /product-details/N.xml sitemap
shards (10 shards, listed at /sitemap.xml), each pointing at /p/<slug> product
pages. Each PDP embeds a Schema.org Product/Offer JSON-LD block server-side.

CURRENCY QUIRK: the JSON-LD `offers.priceCurrency` field is hardcoded to
"AED" store-wide (confirmed across every product checked) even though the
storefront is Iraq-only and every other currency signal disagrees — the
site-config JSON embedded in the page states `"currency":"IQD"`, and the
rendered price text on the page reads e.g. "15,000 دينار" (IQD symbol, not
AED). The JSON-LD price *number* is correct; only the currency label is
wrong. This spider ignores `offers.priceCurrency` and hardcodes IQD.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.mamame.iq"
_SITEMAP_INDEX = f"{_BASE}/sitemap.xml"


class MamameIqSpider(scrapy.Spider):
    name = "mamame_iq"
    allowed_domains = ["mamame.iq", "www.mamame.iq"]
    currency = "IQD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 6,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX, callback=self.parse_index, errback=self.errback
        )

    def parse_index(self, response):
        locs = response.xpath("//*[local-name()='loc']/text()").getall()
        shards = [u for u in locs if "/product-details/" in u]
        logger.info(f"mamame_iq: {len(shards)} product-details sitemap shards")
        for shard in shards:
            yield scrapy.Request(shard, callback=self.parse_shard, errback=self.errback)

    def parse_shard(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/p/" in u]
        logger.info(f"mamame_iq: shard {response.url} -> {len(product_urls)} products")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"mamame_iq: no Product JSON-LD at {response.url}")
            return
        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get("price")
        name = product.get("name")
        if not (price and name):
            return
        brand = product.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name") or brand.get("url")
        yield {
            "product_id": str(product.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "brand": brand,
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": "InStock" in str(offer.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_product(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Product":
                    return c
        return None

    def errback(self, failure):
        logger.error(
            f"mamame_iq: request failed {failure.request.url} — {failure.value!r}"
        )
