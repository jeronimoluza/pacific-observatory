"""
Spider for Redwave (Maldives hypermarket) - https://redwave.mv/

CrawlSpider Pattern A — WooCommerce. PDPs at /product/<slug>/.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)


class RedwaveMvSpider(CrawlSpider):
    name = "redwave_mv"
    allowed_domains = ["redwave.mv", "order.redwave.mv"]
    start_urls = [
        "https://redwave.mv/product-category/groceries/",
        "https://redwave.mv/product-category/groceries/beverages/soft-drinks/",
        "https://redwave.mv/product-category/health-beauty/",
        "https://redwave.mv/product-category/home-appliances/",
        "https://redwave.mv/product-category/households/",
        "https://redwave.mv/product-category/technology-electronics/",
        "https://redwave.mv/product-category/decor-organise/",
        "https://redwave.mv/product-category/furniture/",
        "https://redwave.mv/product-category/all-products/toys/",
        "https://redwave.mv/product-category/all-products/sports-outdoor/",
        "https://redwave.mv/product-category/clearance-sale/",
    ]
    currency = "MVR"

    SELECTORS = {
        "product_name": [
            "h1.product_title.entry-title::text",
            "h1[itemprop='name']::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "p.price ins span.woocommerce-Price-amount bdi::text",
            "p.price span.woocommerce-Price-amount bdi::text",
            "div.summary p.price span.woocommerce-Price-amount::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "nav.woocommerce-breadcrumb a::text",
        ],
        "product_id": [
            "span.sku::text",
            "meta[property='product:retailer_item_id']::attr(content)",
        ],
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/product/[a-z0-9\-]+/?$",
                deny=r"(cart|checkout|account|login|search|add-to-cart=|wp-admin|/brand/|product-category|order-tracking)",
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
