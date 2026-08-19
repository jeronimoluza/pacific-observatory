"""
Spider for Gourmet Versand (Germany) — https://www.gourmet-versand.com/.

Custom in-house PHP storefront (no CMS generator tag). URL discovery via the
Google sitemap listed in robots.txt (sitemap_de.xml, 14,421 URLs; 13,624 of
them are /de/article<id>/... product-detail pages, filtered by that path
segment). Each PDP embeds a Schema.org Product JSON-LD block; unlike most
sites, price lives under offers.priceSpecification.price/priceCurrency, not
offers.price directly (some "TAGESPREIS" truffle/caviar items are unit-priced
per gram via the JSON-LD's own referenceQuantity, which is left as-is rather
than normalized). Confirmed live 2026-08-18, no rendering needed.

Gourmet/delicatessen catalog -- truffles, caviar, cheese, oils. Sample:
"Truffel Winter - Edeltrueffel frisch aus Frankreich..." EUR 2.23/g;
"Desietra Baeriskaya Kaviar... 50 g" EUR 50.99.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.gourmet-versand.com/advertising/google/sitemap_de.xml"


class GourmetVersandDeSpider(scrapy.Spider):
    name = "gourmet_versand_de"
    allowed_domains = ["gourmet-versand.com", "www.gourmet-versand.com"]
    currency = "EUR"
    language = "de"

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
        product_urls = [u for u in urls if "/de/article" in u]
        logger.info(f"gourmet_versand_de: sitemap has {len(product_urls)} product urls")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
            return
        name = product.get("name")
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        currency = offers.get("priceCurrency")
        if price is None:
            spec = offers.get("priceSpecification") or {}
            if isinstance(spec, list):
                spec = spec[0] if spec else {}
            price = spec.get("price")
            currency = currency or spec.get("priceCurrency")
        if not (name and price is not None):
            return
        availability = str(offers.get("availability") or "")
        yield {
            "product_id": str(product.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": currency or self.currency,
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
                if isinstance(c, dict) and c.get("@type") == "Product":
                    return c
        return None

    def errback(self, failure):
        logger.error(
            f"gourmet_versand_de request failed: {failure.request.url} — {failure.value!r}"
        )
