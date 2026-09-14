"""Bison Food Solutions shop (Rwanda) -- https://bison.rw/shop."""

from datetime import datetime, timezone

import scrapy

_BASE = "https://bison.rw"
_CATALOG_API = f"{_BASE}/api/shop/catalog"


class BisonRwSpider(scrapy.Spider):
    name = "bison_rw"
    allowed_domains = ["bison.rw"]
    currency = "RWF"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_CATALOG_API, callback=self.parse_catalog)

    def parse_catalog(self, response):
        try:
            products = response.json()
        except ValueError:
            self.logger.warning("bison_rw: non-JSON response at %s", response.url)
            return
        if not isinstance(products, list):
            self.logger.warning("bison_rw: unexpected payload type at %s", response.url)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            item = self._item(product, scraped_at)
            if item:
                yield item

    def _item(self, product: dict, scraped_at: str):
        product_id = product.get("id")
        name = str(product.get("name") or "").strip()
        price = product.get("final_price")
        if price in (None, ""):
            price = product.get("price")
        if not product_id or not name or price in (None, ""):
            return None

        category = str(product.get("category") or "").strip()
        unit = str(product.get("unit") or "").strip()
        if category and unit:
            category = f"{category} | unit: {unit}"
        elif unit:
            category = f"unit: {unit}"

        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category or None,
            "price": str(price).replace(",", ""),
            "currency": self.currency,
            "available": bool(product.get("in_stock")),
            "url": f"{_BASE}/shop/product/{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
