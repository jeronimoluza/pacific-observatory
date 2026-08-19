"""
Spider for Simma (Iraq) — www.simma.io, multi-vendor marketplace (products
live under per-seller storefronts, e.g. /en/stores/shein/products/<slug>).
Next.js SSR. URL discovery via /sitemap-store-products.xml, listed at the
top-level /sitemap.xml index. Each product URL is emitted three times (ar/en/
ku locale variants); only the /en/ variant is crawled to avoid tripling rows.
Each PDP embeds a Schema.org Product/Offer JSON-LD block server-side with a
correctly-labeled priceCurrency (IQD), confirmed live.
"""

import json
import logging

from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.simma.io"
_SITEMAP_INDEX = f"{_BASE}/sitemap.xml"


class SimmaIoSpider(scrapy.Spider):
    name = "simma_io"
    allowed_domains = ["simma.io", "www.simma.io"]
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
        shards = [u for u in locs if "sitemap-store-products" in u]
        logger.info(f"simma_io: {len(shards)} store-products sitemap shard(s)")
        for shard in shards:
            yield scrapy.Request(shard, callback=self.parse_shard, errback=self.errback)

    def parse_shard(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/en/stores/" in u and "/products/" in u]
        logger.info(f"simma_io: shard -> {len(product_urls)} en product urls")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"simma_io: no Product JSON-LD at {response.url}")
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
            brand = brand.get("name")
        yield {
            "product_id": str(product.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "brand": brand,
            "category": product.get("category"),
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
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
            f"simma_io: request failed {failure.request.url} — {failure.value!r}"
        )
