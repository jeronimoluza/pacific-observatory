"""
Spider for scraping Jianke (China) - https://www.jianke.com/
Extracts product information including prices, categories, and URLs.
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class JiankeSpider(CrawlSpider):
    """
    CrawlSpider for Jianke (China).
    Discovers product pages and extracts price data.
    """

    name = "jianke"
    allowed_domains = ["www.jianke.com"]
    start_urls = [
        "https://www.jianke.com/",
    ]
    country = "china"
    currency = "CNY"

    SELECTORS = get_selectors("jianke")

    rules = (
        # Follow category listing pages (/list-XXXX.html)
        Rule(
            LinkExtractor(
                allow=r"/list-\d+\.html",
                deny=r"(cart|checkout|account|login|search|ask|doctor|hospital|jibing|news|yyzd|help)",
            ),
            follow=True,
        ),
        # Follow disease/condition category pages (which link to products)
        Rule(
            LinkExtractor(
                allow=r"/[a-z]+pd/",
                deny=r"(cart|checkout|account|login|search|ask|doctor|hospital|jibing|news|yyzd|help)",
            ),
            follow=True,
        ),
        # Extract product pages (/product/{id}.html)
        Rule(
            LinkExtractor(
                allow=r"/product/\d+\.html",
                deny=r"(cart|checkout|account|login|search)",
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
