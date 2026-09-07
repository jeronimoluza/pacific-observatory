"""
Spider for VG Mart (Lao PDR) - https://www.vgmart.la/

VG Mart is a Vientiane grocery delivery app/landing site backed by a public
6amMart-style API. The public web landing page has no product catalogue, but
the API exposes the active grocery store, zone, module, and item prices without
login. The current catalogue is tiny, so this source is intentionally
low-yield but passes the five-row evidence gate.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class VgmartLaSpider(scrapy.Spider):
    name = "vgmart_la"
    allowed_domains = ["vgmart.la", "www.vgmart.la"]
    currency = "LAK"
    language = "en"

    API_URL = (
        "https://www.vgmart.la/api/v1/items/latest"
        "?store_id=4&category_id=0&limit=50&offset=1"
    )

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(
            self.API_URL,
            callback=self.parse_items,
            headers={
                "Accept": "application/json",
                "zoneId": "[3]",
                "moduleId": "3",
            },
        )

    def parse_items(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning("non-JSON response at %s", response.url)
            return

        products = data.get("products") or data.get("items") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            product_id = product.get("id")
            name = product.get("name")
            price = product.get("price")
            if product_id is None or not name or price is None:
                continue

            category_names = [
                str(c.get("name"))
                for c in product.get("category_ids", [])
                if isinstance(c, dict) and c.get("name")
            ]
            unit = product.get("unit_type")
            product_name = f"{name} ({unit})" if unit else name

            yield {
                "product_id": str(product_id),
                "product_name": product_name,
                "price": str(price),
                "currency": self.currency,
                "category": " > ".join(category_names) or None,
                "url": f"{response.url}#item-{product_id}",
                "language": self.language,
                "store": product.get("store_name"),
                "stock": product.get("stock"),
                "scraped_at_utc": scraped_at,
            }
            logger.info("Scraped product: %s", name)
