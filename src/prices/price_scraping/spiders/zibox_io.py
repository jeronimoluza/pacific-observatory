"""
Spider for ZiBox (Iraq) — zibox.io, multi-vendor marketplace (first-party
"ZiBox" shop plus third-party shops, e.g. /en/shops/247/Maf-Company). Next.js
SSR. URL discovery via 5 sitemap shards (/sitemaps/products-1.xml ..
products-5.xml), listed at the top-level /sitemap.xml index. Each product URL
is emitted three times (en/ar/ku locale variants); only the /en/ variant is
crawled to avoid tripling rows. Each PDP embeds a Schema.org Product/Offer
JSON-LD block server-side with a correctly-labeled priceCurrency (IQD),
confirmed live.
"""

import json
import logging

from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://zibox.io"
_SITEMAP_INDEX = f"{_BASE}/sitemap.xml"


class ZiboxIoSpider(scrapy.Spider):
    name = "zibox_io"
    allowed_domains = ["zibox.io"]
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
        shards = [u for u in locs if "/sitemaps/products-" in u]
        logger.info(f"zibox_io: {len(shards)} product sitemap shard(s)")
        for shard in shards:
            yield scrapy.Request(shard, callback=self.parse_shard, errback=self.errback)

    def parse_shard(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/en/product/" in u]
        logger.info(f"zibox_io: shard -> {len(product_urls)} en product urls")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"zibox_io: no Product JSON-LD at {response.url}")
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
            f"zibox_io: request failed {failure.request.url} — {failure.value!r}"
        )
