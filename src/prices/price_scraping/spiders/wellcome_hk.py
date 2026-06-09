"""
Spider for Wellcome (Hong Kong supermarket) - https://www.wellcome.com.hk/
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class WellcomeHkSpider(CrawlSpider):
    name = "wellcome_hk"
    allowed_domains = ["wellcome.com.hk", "www.wellcome.com.hk"]
    start_urls = ["https://www.wellcome.com.hk/"]
    currency = "HKD"

    SELECTORS = get_selectors("wellcome_hk")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/zh-hant/wellcome/d/[A-Za-z0-9]+\.html",
            ),
            follow=True,
        ),
        Rule(
            LinkExtractor(
                allow=r"/zh-hant/wellcome/p/.+/i/\d+\.html",
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
