"""
Spider for Shopping-D (Laos online supermarket, Shopify) - https://www.shopping-d.com/
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class ShoppingDSpider(CrawlSpider):
    name = "shopping_d"
    allowed_domains = ["shopping-d.com", "www.shopping-d.com"]
    start_urls = [
        "https://www.shopping-d.com/collections",
    ]
    currency = "LAK"

    SELECTORS = get_selectors("shopping_d")

    rules = (
        # Collections index is paginated (14+ pages) and each collection page
        # is itself paginated; follow both so the crawl discovers every
        # category (fresh produce, dairy, meats, seafood, bakery, etc.)
        # instead of only the 2 collections previously hardcoded.
        Rule(
            LinkExtractor(
                allow=r"/collections(/[^/?#]+)?(\?page=\d+)?$",
                deny=r"(cart|checkout|account|/policies/|search\?)",
            ),
            follow=True,
        ),
        Rule(
            LinkExtractor(
                allow=r"/products/[^/?#]+",
                deny=r"(cart|checkout|account|/policies/|search\?)",
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
