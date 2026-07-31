"""
Spider for Chemist Plus (Shopify) - https://chemistplus.co.nz/

Uses Shopify's public /products.json endpoint: yields one item per variant,
paginates 250 products at a time until the catalog is exhausted.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class ChemistPlusSpider(scrapy.Spider):
    name = "chemist_plus"
    allowed_domains = ["chemistplus.co.nz"]
    base_url = "https://chemistplus.co.nz"
    currency = "NZD"
    page_size = 250

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
