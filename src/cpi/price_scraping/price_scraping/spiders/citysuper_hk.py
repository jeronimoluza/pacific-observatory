"""
Spider for CitySuper (Hong Kong) - https://www.citysuper.com.hk/

CitySuper is a premium supermarket / gourmet food chain in HK running on Shopify.
Strategy mirrors dynamic_vanuatu: page through /products.json?limit=250&page=N
until an empty products list is returned. No Cloudflare, no auth, no JS render.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.citysuper.com.hk/products.json"
_PAGE_SIZE = 250
_PRODUCT_URL_BASE = "https://www.citysuper.com.hk/products"


class CitySuperHkSpider(scrapy.Spider):
    name = "citysuper_hk"
    allowed_domains = ["www.citysuper.com.hk"]
    country = "hong_kong"
    currency = "HKD"
    language = "en"

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
            product_type = product.get("product_type", "") or ""
            url = f"{_PRODUCT_URL_BASE}/{handle}"

            variants = product.get("variants", [])
            if not variants:
                continue

            variant = variants[0]
            sku = variant.get("sku") or product_id
            raw_price = variant.get("price", "")
            if not raw_price:
                logger.warning("No price for product %s (%s)", product_name, url)
                continue

            yield {
                "product_id": sku,
                "product_name": product_name,
                "price": str(raw_price),
                "currency": self.currency,
                "category": product_type,
                "url": url,
                "scraped_at": scraped_at,
            }

        if len(products) == _PAGE_SIZE:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE_URL}?limit={_PAGE_SIZE}&page={next_page}",
                callback=self.parse_products,
                meta={"page": next_page},
            )
