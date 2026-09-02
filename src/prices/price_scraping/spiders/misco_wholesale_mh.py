"""MISCO Wholesale Marshall Islands public product API."""

from __future__ import annotations

from datetime import datetime, timezone

import scrapy


class MiscoWholesaleMhSpider(scrapy.Spider):
    name = "misco_wholesale_mh"
    allowed_domains = ["miscowholesale.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            "https://miscowholesale.com/api/products?limit=100",
            callback=self.parse_products,
            meta={"impersonate": "chrome120"},
        )

    def parse_products(self, response):
        data = response.json()
        products = data.get("products") if isinstance(data, dict) else []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            if not isinstance(product, dict):
                continue
            price = product.get("wholesalePrice")
            name = (product.get("name") or "").strip()
            if price is None or not name:
                continue
            category = product.get("category") or {}
            brand = product.get("brand") or {}
            yield {
                "product_id": str(product.get("sku") or product.get("id")),
                "product_name": name[:500],
                "brand": brand.get("name") if isinstance(brand, dict) else None,
                "category": (
                    category.get("name") if isinstance(category, dict) else None
                ),
                "price": str(price),
                "currency": self.currency,
                "available": (product.get("stock") or 0) > 0,
                "url": f"https://miscowholesale.com/products/{product.get('id')}",
                "language": self.language,
                "moq": product.get("moq"),
                "package_size": product.get("packageSize"),
                "retail_price": product.get("retailPrice"),
                "scraped_at_utc": scraped_at,
            }
