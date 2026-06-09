"""
Spider for Coles (Australia supermarket) - https://www.coles.com.au/
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class ColesAuSpider(CrawlSpider):
    name = "coles_au"
    allowed_domains = ["coles.com.au", "www.coles.com.au"]
    start_urls = [
        "https://www.coles.com.au/browse/fruit-vegetables",
        "https://www.coles.com.au/browse/dairy-eggs-fridge",
        "https://www.coles.com.au/browse/meat-seafood",
        "https://www.coles.com.au/browse/bakery",
        "https://www.coles.com.au/browse/pantry",
        "https://www.coles.com.au/browse/frozen",
        "https://www.coles.com.au/browse/drinks",
        "https://www.coles.com.au/browse/deli",
    ]
    currency = "AUD"

    SELECTORS = get_selectors("coles_au")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/browse/[a-z0-9-]+(\?page=\d+)?$",
            ),
            follow=True,
        ),
        Rule(
            LinkExtractor(
                allow=r"/product/[a-z0-9-]+-\d+/?$",
                deny=r"(cart|checkout|account|login|search)",
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
