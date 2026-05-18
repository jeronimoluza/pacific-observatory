"""
Spider for ePharmacy Nepal - https://www.epharmacy.com.np/

CrawlSpider Pattern A — server-rendered HTML. PDPs at /<long-product-slug>.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)


class EpharmacyNpSpider(CrawlSpider):
    name = "epharmacy_np"
    allowed_domains = ["epharmacy.com.np", "www.epharmacy.com.np"]
    start_urls = [
        "https://www.epharmacy.com.np/baby-care",
        "https://www.epharmacy.com.np/personal-care",
        "https://www.epharmacy.com.np/health-supplements",
        "https://www.epharmacy.com.np/skin-care",
    ]
    currency = "NPR"

    SELECTORS = {
        "product_name": [
            "h1.product-name::text",
            "h1[itemprop='name']::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "meta[itemprop='price']::attr(content)",
            "span.actual-price::text",
            "div.actual-price::text",
            ".actual-price::text",
            "div.product-price span.price-value::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "div.sku span::text",
        ],
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/[a-z0-9\-]{20,}$",
                deny=r"(cart|checkout|login|search|/about|/contact|/blog|/policy|/producttag/|/products-under-|/categories|/baby-care$|/personal-care$|/health-supplements$|/skin-care$|/face-care$|/oral-care$|/hair-care$)",
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
