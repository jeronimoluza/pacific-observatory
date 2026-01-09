"""
Spider for scraping Pickaroo (Philippines) - https://pickaroo.com/
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


class PickarooSpider(CrawlSpider):
    """
    CrawlSpider for Pickaroo (Philippines).
    Discovers product pages and extracts price data.
    """

    name = "pickaroo"
    allowed_domains = ["pickaroo.com"]
    start_urls = ["https://pickaroo.com/groceries/brands/supermarket/"]
    country = "philippines"
    currency = "PHP"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("pickaroo")

    # Rules for following links and extracting data
    rules = (
        # Rule 1: Follow brand/supermarket links from start page
        # Examples: /sr/, /pasig-fresh-market/
        Rule(
            LinkExtractor(
                allow=r"^https://pickaroo\.com/[^/]+/$",
                deny=r"(cart|checkout|account|login|search|groceries)",
            ),
            follow=True,
        ),
        # Rule 2: Follow location/store links
        # Examples: /sr/products/sr-nuvali, /pasig-fresh-market/products/pasig-fresh-market
        Rule(
            LinkExtractor(
                allow=r"^https://pickaroo\.com/[^/]+/products/[^/]+$",
            ),
            follow=True,
        ),
        # Rule 3: Extract product pages
        # Examples: /pasig-fresh-market/products/pasig-fresh-market/product-detail/18061/calamansi-kalamansi
        Rule(
            LinkExtractor(
                allow=r"/product-detail/\d+/",
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
        details = extractor.extract("details", self.SELECTORS["details"])

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
                "details": details,
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
