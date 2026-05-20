"""
Spider for scraping MH Online (Fiji) - https://mh.com.fj/
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


class MhOnlineSpider(CrawlSpider):
    """
    CrawlSpider for MH Online (Fiji).
    Discovers product pages and extracts price data.
    """

    name = "mh_online"
    allowed_domains = ["mh.com.fj"]
    start_urls = ["https://mh.com.fj/shop/"]
    currency = "FJ"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("mh_online")

    # Rules for following links and extracting data
    rules = (
        # Follow category links
        Rule(
            LinkExtractor(
                allow=r"/product/.*",
                deny=r"(cart|checkout|account|login|search\?)",
            ),
            callback="parse_product",
            follow=True,
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
        category = extractor.extract(
            "category", self.SELECTORS["category"], method="getall"
        )
        product_id = extractor.extract("product_id", self.SELECTORS["product_id"])
        url = response.url

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
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
