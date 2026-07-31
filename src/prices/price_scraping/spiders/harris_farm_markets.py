"""
Spider for Harris Farm Markets (Australia) - https://www.harrisfarm.com.au
Shopify-hosted storefront. Uses the standard Shopify collection JSON endpoint
(/collections/<handle>/products.json) directly - no Playwright, no auth.
Plain requests work fine (verified 200 with a browser UA, no impersonation
needed); RandomBrowserMiddleware is disabled to keep requests simple/fast.
"""

import logging

import scrapy

logger = logging.getLogger(__name__)


class HarrisFarmMarketsSpider(scrapy.Spider):
    name = "harris_farm_markets"
    allowed_domains = ["www.harrisfarm.com.au"]
    currency = "AUD"

    COLLECTION_HANDLE = "buy-groceries-online"
    PAGE_SIZE = 250

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
    }

    def start_requests(self):
        url = (
            f"https://www.harrisfarm.com.au/collections/{self.COLLECTION_HANDLE}"
            f"/products.json?limit={self.PAGE_SIZE}&page=1"
        )
        yield scrapy.Request(url, callback=self.parse, meta={"page": 1})

    def parse(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        products = payload.get("products") or []
        page = response.meta["page"]
        logger.info(f"harris_farm_markets: page={page} products={len(products)}")

        for prod in products:
            title = prod.get("title")
            product_type = prod.get("product_type")
            handle = prod.get("handle")
            variants = prod.get("variants") or []
            for variant in variants:
                if not variant.get("available"):
                    continue
                price = variant.get("price")
                if not title or not price:
                    continue
                variant_title = variant.get("title")
                name = (
                    title
                    if variant_title in (None, "Default Title")
                    else f"{title} ({variant_title})"
                )
                yield {
                    "product_id": str(
                        variant.get("sku") or variant.get("id") or prod.get("id")
                    ),
                    "product_name": name,
                    "price": str(price),
                    "currency": self.currency,
                    "category": product_type or None,
                    "url": f"https://www.harrisfarm.com.au/products/{handle}?variant={variant.get('id')}"
                    if handle
                    else None,
                    "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
                }

        if products:
            next_page = page + 1
            next_url = (
                f"https://www.harrisfarm.com.au/collections/{self.COLLECTION_HANDLE}"
                f"/products.json?limit={self.PAGE_SIZE}&page={next_page}"
            )
            yield scrapy.Request(
                next_url, callback=self.parse, meta={"page": next_page}
            )
