"""
Spider for scraping Horizon Farms (Japan) - https://en.horizonfarms.jp/
Extracts product information including prices, categories, and URLs.
Category is extracted from the URL path (e.g., 'free-range-pork' from /collections/free-range-pork).
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class HorizonFarmsSpider(CrawlSpider):
    """
    CrawlSpider for Horizon Farms (Japan).
    Discovers product pages from category pages and extracts price data.
    """

    name = "horizon_farms"
    allowed_domains = ["en.horizonfarms.jp"]
    start_urls = ["https://en.horizonfarms.jp/"]
    country = "japan"
    currency = "JPY"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("horizon_farms")

    # Rules for following links and extracting data
    rules = (
        # Rule 1: Follow category pages from homepage
        # Examples: /collections/free-range-pork, /collections/organic-butter
        Rule(
            LinkExtractor(
                allow=r"/collections/[^/]+$",
                deny=r"(cart|checkout|account|login|search)",
            ),
            callback="parse_category",
            follow=True,
        ),
        # Rule 2: Extract product pages from category pages
        # Examples: /products/cd661
        Rule(
            LinkExtractor(
                allow=r"/products/[^/]+$",
            ),
            callback="parse_product",
            follow=False,
        ),
    )

    def parse_category(self, response):
        """
        Parse category page to extract category name and follow product links.
        Category name is extracted from URL path.
        """
        # Extract category from URL: /collections/free-range-pork -> free-range-pork
        category = None
        if "/collections/" in response.url:
            category = response.url.split("/collections/")[-1].rstrip("/")

        # Store category in meta for product pages
        for product_link in response.css("a[href*='/products/']::attr(href)").getall():
            yield response.follow(
                product_link, callback=self.parse_product, meta={"category": category}
            )

    def parse_product(self, response):
        """
        Parse product page and extract relevant data.
        Category is passed from the category page via meta.
        """
        # Initialize extractor with fallback selectors
        extractor = SelectorExtractor(response, logger)

        # Extract product information using fallback selectors
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        details = extractor.extract("details", self.SELECTORS["details"])

        # Debug logging to see extracted values
        logger.debug(
            f"Extracted product_name: '{product_name}' (type: {type(product_name)})"
        )
        logger.debug(f"Extracted price: '{price}' (type: {type(price)})")
        logger.debug(f"Extracted details: '{details}' (type: {type(details)})")

        url = response.url
        # Get category from meta (passed from category page)
        category = response.meta.get("category")

        if product_name and price:
            yield {
                "product_name": product_name,
                "category": category,
                "price": price,
                "details": details,
                "currency": self.currency,
                "url": url,
                "scraped_at": response.headers.get("Date", "").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name} (category: {category})")
        else:
            logger.warning(f"Could not extract product data from {response.url}")

    def parse_start_url(self, response):
        """
        Parse the start URL to discover category links.
        This is called automatically by CrawlSpider for start_urls.
        """
        # Extract category links from homepage that match /collections/ pattern
        category_links = response.css("a[href*='/collections/']::attr(href)").getall()
        for link in category_links:
            # Use parse_category to handle category pages
            yield response.follow(link, callback=self.parse_category)
