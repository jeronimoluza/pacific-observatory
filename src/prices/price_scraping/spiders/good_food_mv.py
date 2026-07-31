"""
Spider for Good Food Maldives (Shopify) - https://www.goodfoodmaldives.com/

Uses Shopify's public /products.json endpoint: yields one item per variant,
paginates 250 products at a time until the catalog is exhausted.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class GoodFoodMvSpider(scrapy.Spider):
    name = "good_food_mv"
    allowed_domains = ["goodfoodmaldives.com", "www.goodfoodmaldives.com"]
    base_url = "https://www.goodfoodmaldives.com"
    currency = "MVR"
    page_size = 250

    # Site returns 429 under default concurrency; throttle to a single
    # in-flight request per domain with a delay.
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
    }

    async def start(self):
        yield scrapy.Request(
            f"{self.base_url}/products.json?limit={self.page_size}&page=1",
            callback=self.parse_products,
            meta={"page": 1},
        )

    def parse_products(self, response):
        data = json.loads(response.text)
        products = data.get("products", [])
        if not products:
            return

        scraped_at = response.headers.get("Date", b"").decode("utf-8")
        for product in products:
            category = product.get("product_type") or None
            for variant in product.get("variants", []):
                price = variant.get("price")
                if not price:
                    continue
                variant_title = variant.get("title")
                title = product["title"]
                if variant_title and variant_title != "Default Title":
                    title = f"{title} - {variant_title}"
                yield {
                    "product_id": variant.get("sku") or str(variant["id"]),
                    "product_name": title,
                    "price": price,
                    "currency": self.currency,
                    "category": category,
                    "url": f"{self.base_url}/products/{product['handle']}?variant={variant.get('id')}",
                    "scraped_at": scraped_at,
                }

        next_page = response.meta["page"] + 1
        yield scrapy.Request(
            f"{self.base_url}/products.json?limit={self.page_size}&page={next_page}",
            callback=self.parse_products,
            meta={"page": next_page},
        )
