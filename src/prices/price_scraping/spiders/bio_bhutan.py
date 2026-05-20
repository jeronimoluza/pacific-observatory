"""
Spider for Bio Bhutan (organic natural products) - https://biobhutan.com/

CrawlSpider Pattern A — WooCommerce. PDPs at /product/<slug>/.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)


class BioBhutanSpider(CrawlSpider):
    name = "bio_bhutan"
    allowed_domains = ["biobhutan.com"]
    start_urls = [
        "https://biobhutan.com/shop/",
        "https://biobhutan.com/product-category/herbal-teas/",
        "https://biobhutan.com/product-category/natural-handmade-soap-bar/",
        "https://biobhutan.com/product-category/non-wood-forest-products/",
        "https://biobhutan.com/product-category/organic-spices/",
        "https://biobhutan.com/product-category/pure-essential-oils-and-fragrances/",
    ]
    currency = "BTN"

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
                deny=r"(cart|checkout|account|login|search|add-to-cart=|wp-admin|product-category)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS["category"], method="getall"
        )
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
