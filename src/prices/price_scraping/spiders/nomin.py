"""
Spider for Nomin (Mongolian hypermarket) - https://nomin.mn/
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class NominSpider(CrawlSpider):
    name = "nomin"
    allowed_domains = ["nomin.mn", "www.nomin.mn"]
    start_urls = [
        "https://www.nomin.mn/t/sales",
        "https://www.nomin.mn/t/beleg",
    ]
    currency = "MNT"

    SELECTORS = get_selectors("nomin")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/p/\d+",
                deny=r"(/cart|/checkout|/login|/register|/account|/wishlist)",
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
            "category", self.SELECTORS.get("category", []), method="getall"
        )
        product_id = extractor.extract(
            "product_id", self.SELECTORS.get("product_id", [])
        )

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")
