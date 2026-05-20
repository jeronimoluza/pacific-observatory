"""
Spider for scraping CityPharm (Mongolia) - https://citypharm.mn/
Extracts product information including prices, categories, and URLs.
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class CityPharmSpider(CrawlSpider):
    """
    CrawlSpider for CityPharm (Mongolia).
    Discovers product pages and extracts price data.
    """

    name = "citypharm"
    allowed_domains = ["citypharm.mn"]
    start_urls = [
        "https://citypharm.mn/shop",
    ]
    currency = "MNT"

    SELECTORS = get_selectors("citypharm")

    rules = (
        # Follow category links
        Rule(
            LinkExtractor(
                allow=r"/shop/category/",
                deny=r"(cart|checkout|account|login|search|wishlist|change_pricelist)",
            ),
            follow=True,
        ),
        # Follow pagination
        Rule(
            LinkExtractor(
                allow=r"/shop\?.*page=\d+",
            ),
            follow=True,
        ),
        # Extract product pages (Odoo pattern: /shop/{id}-{name}-{number})
        Rule(
            LinkExtractor(
                allow=r"/shop/\d+-",
                deny=r"(cart|checkout|account|login|search|wishlist|change_pricelist|/shop/category/)",
            ),
            callback="parse_product",
            follow=False,
        ),
    )

    def parse_product(self, response):
        """Parse product page and extract relevant data."""
        extractor = SelectorExtractor(response, logger)

        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS["category"], method="getall"
        )

        if product_name and price:
            yield {
                "product_name": product_name,
                "category": " > ".join(category) if category else None,
                "price": price,
                "currency": self.currency,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")
