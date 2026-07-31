"""
Spider for Lemon Farm (Thailand) - https://shop.lemonfarm.com
Organic-grocery chain on a standard Shopify storefront. Uses the public
`/products.json` endpoint directly (no auth, no Playwright required).
Product titles are Thai regardless of `/en` vs bare host path — only the
storefront chrome localizes, not the catalog data.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class LemonFarmSpider(scrapy.Spider):
    name = "lemon_farm"
    allowed_domains = ["shop.lemonfarm.com"]
    currency = "THB"

    PAGE_SIZE = 250
    MAX_PAGES = 20

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def start_requests(self):
        yield self._page_request(1)

    def _page_request(self, page):
        url = f"https://shop.lemonfarm.com/products.json?limit={self.PAGE_SIZE}&page={page}"
        return scrapy.Request(
            url,
            headers={"Accept": "application/json"},
            callback=self.parse_page,
            meta={"page": page},
        )

    def parse_page(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        products = payload.get("products") or []
        page = response.meta["page"]
        logger.info(f"lemon_farm: page={page} products={len(products)}")

        for p in products:
            variant = (p.get("variants") or [{}])[0]
            price = variant.get("price")
            name = p.get("title")
            if not name or not price:
                continue
            handle = p.get("handle")
            yield {
                "product_id": str(variant.get("id")) if variant.get("id") else None,
                "product_name": name,
                "price": str(price),
                "currency": self.currency,
                "category": p.get("product_type") or None,
                "url": f"https://shop.lemonfarm.com/products/{handle}?variant={variant.get('id')}"
                if handle
                else None,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        if products and page < self.MAX_PAGES:
            yield self._page_request(page + 1)
