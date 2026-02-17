"""
Spider for scraping South Star Drug (Philippines) - https://southstardrug.com.ph/
Extracts product information including prices, categories, and URLs.
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class SouthStarDrugSpider(CrawlSpider):
    """
    CrawlSpider for South Star Drug (Philippines).
    Discovers product pages and extracts price data.
    """

    name = "south_star_drug"
    allowed_domains = ["southstardrug.com.ph"]
    start_urls = [
        "https://southstardrug.com.ph/collections/medicines",
        "https://southstardrug.com.ph/collections/vitamins-supplements",
        "https://southstardrug.com.ph/collections/personal-care",
        "https://southstardrug.com.ph/collections/baby-care",
        "https://southstardrug.com.ph/collections/medical-supplies",
        "https://southstardrug.com.ph/collections/beauty",
    ]
    country = "philippines"
    currency = "PHP"

    SELECTORS = get_selectors("south_star_drug")

    rules = (
        # Follow collection/category links
        Rule(
            LinkExtractor(
                allow=r"/collections/",
                deny=r"(cart|checkout|account|login|search)",
            ),
            follow=True,
        ),
        # Follow pagination
        Rule(
            LinkExtractor(
                allow=r"/collections/.*\?.*page=\d+",
            ),
            follow=True,
        ),
        # Extract product pages
        Rule(
            LinkExtractor(
                allow=r"/products/",
                deny=r"(cart|checkout|account|login|search|/collections/)",
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
