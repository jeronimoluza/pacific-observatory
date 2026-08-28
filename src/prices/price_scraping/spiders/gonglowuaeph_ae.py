"""
Spider for Go N' Glow (UAE) — https://www.gonglowuaeph.com/.

Wix storefront (server-rendered, "Wix.com Website Builder" generator tag).
Product URLs discovered via the Wix-generated
/store-products-sitemap.xml (1,664 URLs, all under /product-page/, no
category/blog noise). Each PDP embeds a single Schema.org Product JSON-LD
block with name + AED price -- confirmed live 2026-08-18, no rendering
needed. Wix's JSON-LD is inconsistently cased ("Offers"/"offers",
"Availability"/"availability"), so key lookup is case-insensitive.

Sample confirmed: "GMEELAN PEACH NIACINAMIDE WHITENING SERUM" AED 30.00.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.gonglowuaeph.com/store-products-sitemap.xml"


def _ci_get(d: dict, key: str):
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return None


class GonglowuaephAeSpider(scrapy.Spider):
    name = "gonglowuaeph_ae"
    allowed_domains = ["gonglowuaeph.com", "www.gonglowuaeph.com"]
    currency = "AED"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_URL, callback=self.parse_sitemap, errback=self.errback
        )

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/product-page/" in u]
        logger.info(f"gonglowuaeph_ae: sitemap has {len(product_urls)} product urls")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
            return
        name = product.get("name")
        offers = _ci_get(product, "offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = _ci_get(offers, "price")
        if not (name and price is not None):
            return
        availability = str(_ci_get(offers, "availability") or "")
        yield {
            "product_id": str(product.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": _ci_get(offers, "priceCurrency") or self.currency,
            "available": "instock" in availability.lower() if availability else True,
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
            candidates = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            for c in candidates:
                if isinstance(c, dict) and str(c.get("@type", "")).lower() == "product":
                    return c
        return None

    def errback(self, failure):
        logger.error(
            f"gonglowuaeph_ae request failed: {failure.request.url} — {failure.value!r}"
        )
