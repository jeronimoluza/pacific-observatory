"""
Spider for Othoba (Bangladesh general e-commerce) - https://othoba.com/

CrawlSpider Pattern A — server-rendered HTML. PDP URLs are /<slug>-<6+digit-id>.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)


class OthobaSpider(CrawlSpider):
    name = "othoba"
    allowed_domains = ["othoba.com"]
    start_urls = [
        "https://othoba.com/daily-bazar",
        "https://othoba.com/health-beauty",
        "https://othoba.com/home-living",
    ]
    currency = "BDT"

    SELECTORS = {
        "product_name": [
            "h1.product-title::text",
            "h1[itemprop='name']::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "span.new-price::text",
            "div.prices span.new-price::text",
            "span[class*='price-value-']::text",
            "span.non-discounted-price::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "div.breadcrumbs ul li a::text",
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
                allow=r"/[a-z0-9\-]+-\d{4,8}$",
                deny=r"(cart|checkout|account|login|search|tel:|boimela|tag/|tags/)",
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
