"""
Spider for scraping Kioskana (Indonesia) - https://kioskana.com/
Extracts product information including prices, categories, store locations, and URLs.
"""

import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urljoin
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class KioskanaSpider(CrawlSpider):
    """
    CrawlSpider for Kioskana (Indonesia) - https://kioskana.com/
    Discovers product pages and extracts price data.
    """

    name = "kioskana"
    allowed_domains = ["kioskana.com"]
    start_urls = ["https://www.kioskana.com/"]
    country = "indonesia"
    currency = "IDR"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("kioskana")

    # Rules for following links and extracting data
    rules = (
        # Rule 1: Follow main category pages
        # Examples: /collections/all
        Rule(
            LinkExtractor(
                allow=r"/product-category/[^/]+/$",
                deny=r"(cart|checkout|account|login|search|page)",
            ),
            follow=True,
        ),
        # Rule 2: Follow subcategory pages
        # Examples: /product-category/home-garden/benih-tanaman/
        Rule(
            LinkExtractor(
                allow=r"/product-category/[^/]+/[^/]+/$",
                deny=r"(cart|checkout|account|login|search|page)",
            ),
            follow=True,
        ),
        # Rule 3: Extract product pages
        # Examples: /product/kioskana-cooling-element-1-pc-for-shipping-fresh-and-frozen-items/
        Rule(
            LinkExtractor(
                allow=r"/product/[^/]+/$",
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

        if product_name and price:
            yield {
                "product_name": product_name,
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
