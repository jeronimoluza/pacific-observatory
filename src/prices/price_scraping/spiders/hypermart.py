"""
Spider for scraping Hypermart (Indonesia) - https://shop.hypermart.co.id/
Extracts product information including prices, categories, and URLs.
"""

import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urljoin
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class HypermartSpider(CrawlSpider):
    """
    CrawlSpider for Hypermart (Indonesia).
    Discovers product pages and extracts price data.
    """

    name = "hypermart"
    allowed_domains = ["shop.hypermart.co.id"]
    start_urls = ["https://shop.hypermart.co.id/hypermart/"]
    currency = "IDR"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("hypermart")

    # Rules for following links and extracting data
    rules = (
        # Rule 1: Follow category pages
        # Examples: /hypermart/category/D1-GROCERY
        Rule(
            LinkExtractor(
                allow=r"/hypermart/category/[^/\?]+$",
                deny=r"(cart|checkout|account|login|search)",
            ),
            follow=True,
        ),
        # Rule 2: Follow pagination within categories
        # Examples: /hypermart/category/D1-GROCERY?st=20, ?st=40, ?st=60
        Rule(
            LinkExtractor(
                allow=r"/hypermart/category/[^/]+\?st=\d+",
            ),
            follow=True,
        ),
        # Rule 3: Extract product pages
        # Examples: /hypermart/product/HYPERMART-VALUE-PLUS-BUBUK-LADA-HITAM-REFILL-60-GR-36369887
        Rule(
            LinkExtractor(
                allow=r"/hypermart/product/[^/]+$",
                deny=r"(cart|checkout|account|login|search)",
            ),
            callback="parse_product",
            follow=False,
        ),
    )

    def parse_product(self, response):
        """
        Parse product page and extract relevant data.
        """
        # Initialize extractor with fallback selectors
        extractor = SelectorExtractor(response, logger)

        # Extract product information using fallback selectors
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])

        url = response.url
        category = extractor.extract(
            "category", self.SELECTORS["category"], method="getall"
        )
        if product_name and price:
            yield {
                "product_name": product_name,
                "category": " > ".join(category) if category else None,
                "price": price,
                "currency": self.currency,
                "url": url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")

    def parse_start_url(self, response):
        """
        Parse the start URL to discover category links.
        """
        # Extract category links from homepage
        category_links = response.css("a.category-link::attr(href)").getall()
        for link in category_links:
            yield scrapy.Request(
                urljoin(response.url, link),
                callback=self.parse_product,
                dont_obey_robotstxt=False,
            )
