"""
Spider for OnlineSaathi (Nepal general e-commerce) - https://onlinesaathi.com/

CrawlSpider Pattern A — PDPs at /<long-product-slug>.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)


class OnlinesaathiSpider(CrawlSpider):
    name = "onlinesaathi"
    allowed_domains = ["onlinesaathi.com"]
    start_urls = [
        "https://onlinesaathi.com/mobiles",
        "https://onlinesaathi.com/laptops",
        "https://onlinesaathi.com/home-kitchen",
        "https://onlinesaathi.com/tvs",
    ]
    currency = "NPR"

    SELECTORS = {
        "product_name": [
            "h1.prd-main-name::text",
            "h1.product-name::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "div.prd-main-price::text",
            ".prd-main-price::text",
            "div.deliver-price::text",
            "span.price-now::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "ul.breadcrumb li a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "span.sku::text",
        ],
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/[a-z0-9\-]{30,}$",
                deny=r"(cart|checkout|login|search|/about|/contact|/blog|wp-admin|/category|page=)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract("category", self.SELECTORS["category"], method="getall")
        product_id = extractor.extract("product_id", self.SELECTORS["product_id"])

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        else:
            logger.warning(f"Could not extract product data from {response.url}")
