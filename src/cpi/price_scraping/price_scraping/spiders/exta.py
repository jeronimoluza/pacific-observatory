"""
Spider for scraping Exta (Thailand) - https://www.exta.co.th/
Extracts product information including prices, categories, and URLs.
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class ExtaSpider(CrawlSpider):
    """
    CrawlSpider for Exta (Thailand).
    Discovers product pages and extracts price data.
    """

    name = "exta"
    allowed_domains = ["www.exta.co.th", "allonline.7eleven.co.th"]
    start_urls = [
        "https://www.exta.co.th/product-category/bestsaller/",
        "https://www.exta.co.th/product-category/beautiful-skin/",
        "https://www.exta.co.th/product-category/body-lotion/",
        "https://www.exta.co.th/product-category/collagen/",
        "https://www.exta.co.th/product-category/eye-health/",
        "https://www.exta.co.th/product-category/fiber/",
        "https://www.exta.co.th/product-category/acne-jel/",
        "https://www.exta.co.th/product-category/exta-natural/",
    ]
    country = "thailand"
    currency = "THB"

    SELECTORS = get_selectors("exta")

    rules = (
        # Follow product category links
        Rule(
            LinkExtractor(
                allow=r"/product-category/",
                deny=r"(cart|checkout|account|login|search|my-account)",
            ),
            follow=True,
        ),
        # Follow pagination
        Rule(
            LinkExtractor(
                allow=r"/page/\d+",
            ),
            follow=True,
        ),
        # Extract product pages
        Rule(
            LinkExtractor(
                allow=r"/product/[^/]+",
                deny=r"(cart|checkout|account|login|search|product-category|#)",
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
