"""
Spider for Mustafa Centre Singapore - https://shopmustafa.sg/
Shopify storefront exposing the public /products.json feed; yields one item
per variant, paginating 250 products at a time until the catalog is exhausted.
Wide hypermarket catalog (groceries, electronics, household), prices in SGD.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_GENERIC_TAGS = {"new", "sale", "featured", "best seller"}


class MustafaOnlineSpider(scrapy.Spider):
    name = "mustafa_online"
    allowed_domains = ["shopmustafa.sg"]
    base_url = "https://shopmustafa.sg"
    currency = "SGD"
    language = "en"
    page_size = 250

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 6,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
    }

    async def start(self):
        yield scrapy.Request(
            f"{self.base_url}/products.json?limit={self.page_size}&page=1",
            callback=self.parse_products,
            meta={"page": 1},
            headers={"Accept": "application/json"},
        )

    def parse_products(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("mustafa_online: non-JSON response %s", response.url)
            return

        products = data.get("products", [])
        if not products:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            category = product.get("product_type") or None
            if not category:
                tags = product.get("tags") or []
                specific = [t for t in tags if t.lower() not in _GENERIC_TAGS]
                category = (specific or tags or [None])[0]
            handle = product.get("handle")
            title = product.get("title")
            if not title or not handle:
                continue
            for variant in product.get("variants", []):
                price = variant.get("price")
                if not price:
                    continue
                variant_title = variant.get("title")
                full_title = title
                if variant_title and variant_title != "Default Title":
                    full_title = f"{title} - {variant_title}"
                yield {
                    "product_id": variant.get("sku")
                    or variant.get("barcode")
                    or str(variant.get("id")),
                    "product_name": full_title,
                    "price": price,
                    "currency": self.currency,
                    "category": category,
                    "url": f"{self.base_url}/products/{handle}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

        next_page = response.meta["page"] + 1
        yield scrapy.Request(
            f"{self.base_url}/products.json?limit={self.page_size}&page={next_page}",
            callback=self.parse_products,
            meta={"page": next_page},
            headers={"Accept": "application/json"},
        )
