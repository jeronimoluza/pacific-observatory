"""
Spider for scraping Dynamic Vanuatu (Vanuatu) - https://retail.dynamicvanuatu.com/
Extracts product information including prices, categories, and URLs.

Strategy (2026-05-06):
  The HTML crawl approach was hitting HTTP 429 rate-limits on every request
  (208/211 responses were 429 in the 2026-05-05 run). The site is a Shopify
  store and exposes the standard Shopify products.json API which returns JSON
  with no rate-limiting issues. We page through /products.json?limit=250&page=N
  until an empty products list is returned.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://retail.dynamicvanuatu.com/products.json"
_PAGE_SIZE = 250


class DynamicVanuatuSpider(scrapy.Spider):
    """
    Spider for Dynamic Vanuatu (Vanuatu).
    Uses the Shopify products.json JSON API — no HTML crawling.
    """

    name = "dynamic_vanuatu"
    allowed_domains = ["retail.dynamicvanuatu.com"]
    country = "vanuatu"
    currency = "VUV"

    def start_requests(self):
        yield scrapy.Request(
            f"{_BASE_URL}?limit={_PAGE_SIZE}&page=1",
            callback=self.parse_products,
            meta={"page": 1},
        )

    def parse_products(self, response):
        page = response.meta["page"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON on page %d: %s", page, response.url)
            return

        products = data.get("products", [])
        logger.info("Page %d: received %d products", page, len(products))

        if not products:
            logger.info("Empty products list on page %d — crawl complete", page)
            return

        scraped_at = response.headers.get("Date", b"").decode("utf-8")

        for product in products:
            product_id = str(product.get("id", ""))
            product_name = product.get("title", "")
            handle = product.get("handle", "")
            product_type = product.get("product_type", "")
            url = f"https://retail.dynamicvanuatu.com/products/{handle}"

            variants = product.get("variants", [])
            if not variants:
                continue

            # Use first available variant as the canonical price
            variant = variants[0]
            sku = variant.get("sku", product_id)
            raw_price = variant.get("price", "")

            # Shopify returns price as a string of integer centavos (no decimal
            # for VUV since it has no minor unit). Emit as "<amount>VT" to match
            # the existing schema seen in historical JSONL files.
            if raw_price:
                try:
                    price_str = f"{int(raw_price)}VT"
                except (ValueError, TypeError):
                    price_str = str(raw_price)
            else:
                logger.warning("No price for product %s (%s)", product_name, url)
                continue

            yield {
                "product_id": sku or product_id,
                "product_name": product_name,
                "price": price_str,
                "currency": self.currency,
                "category": product_type,
                "url": url,
                "scraped_at": scraped_at,
            }

        # If we got a full page, request the next one
        if len(products) == _PAGE_SIZE:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE_URL}?limit={_PAGE_SIZE}&page={next_page}",
                callback=self.parse_products,
                meta={"page": next_page},
            )
