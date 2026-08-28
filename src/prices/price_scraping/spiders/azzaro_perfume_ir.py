"""
Azzaro Perfume (azzaro-perfume.ir) — Iranian perfume/fragrance retailer.

URL discovery via /sitemap-product.xml (product URLs under /product/<id>/
<slug>/). Each product page exposes Schema.org Product JSON-LD (name,
brand, offers.price/priceCurrency) directly in server-rendered HTML -- no
JS rendering needed. Verified live 2026-08-18: offers.priceCurrency is
"IRR" already (not Toman) -- no unit conversion needed, unlike the
WooCommerce/Toman sources onboarded alongside this one. WooCommerce Store
API returns 418 on this domain (not a Woo store); this is a different
platform sharing the same sitemap-static/brand/category/product/tag/
page/blog shape as anjelagallery_ir (also onboarded from this batch).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://azzaro-perfume.ir/sitemap-product.xml"


class AzzaroPerfumeIrSpider(scrapy.Spider):
    name = "azzaro_perfume_ir"
    allowed_domains = ["azzaro-perfume.ir"]
    currency = "IRR"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_URL,
            callback=self.parse_sitemap,
            errback=self.errback,
        )

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/product/" in u]
        logger.info(
            f"sitemap: {len(urls)} urls total, queued {len(product_urls)} products"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
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
            "category": None,
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
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
