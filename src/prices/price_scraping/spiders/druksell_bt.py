"""
Spider for Druksell (Bhutan, Shopify) - https://druksell.bt/

Shopify public products JSON with scrapy-impersonate Safari TLS profile.
Yields one item per variant and paginates until Shopify returns no products.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class DruksellBtSpider(scrapy.Spider):
    name = "druksell_bt"
    allowed_domains = ["druksell.bt"]
    base_url = "https://druksell.bt"
    currency = "BTN"
    page_size = 250

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.25,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        yield self._products_request(1)

    def _products_request(self, page: int) -> scrapy.Request:
        return scrapy.Request(
            f"{self.base_url}/products.json?limit={self.page_size}&page={page}",
            callback=self.parse_products,
            meta={"impersonate": self.IMPERSONATE_PROFILE, "page": page},
            errback=self.errback,
        )

    def parse_products(self, response):
        page = response.meta["page"]
        data = json.loads(response.text)
        products = data.get("products", [])
        if not products:
            logger.info(f"page={page} products=0")
            return

        yielded = 0
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            title = (product.get("title") or "").strip()
            if not title:
                continue
            category = product.get("product_type") or None
            handle = product.get("handle")
            url = f"{self.base_url}/products/{handle}" if handle else self.base_url

            for variant in product.get("variants", []):
                price = variant.get("price")
                if price in (None, ""):
                    continue
                product_id = variant.get("sku") or variant.get("id")
                if not product_id:
                    continue
                yielded += 1
                yield {
                    "product_id": str(product_id),
                    "product_name": title[:500],
                    "category": category,
                    "price": str(price).replace(",", "").strip(),
                    "currency": self.currency,
                    "url": url,
                    "scraped_at_utc": scraped_at,
                }

        logger.info(f"page={page} products={len(products)} yielded={yielded}")
        yield self._products_request(page + 1)

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} - {failure.value!r}")
