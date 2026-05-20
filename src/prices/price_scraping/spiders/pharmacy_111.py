"""
Spider for scraping 111 Pharmacy (China) - https://m.111.com.cn/
Extracts product information including prices, categories, and URLs.
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class Pharmacy111Spider(CrawlSpider):
    """
    CrawlSpider for 111 Pharmacy (China).
    Discovers product pages and extracts price data.
    """

    name = "pharmacy_111"
    allowed_domains = ["m.111.com.cn", "www.111.com.cn"]
    start_urls = [
        "https://m.111.com.cn/",
    ]
    currency = "CNY"

    SELECTORS = get_selectors("pharmacy_111")

    rules = (
        # Follow category/listing pages
        Rule(
            LinkExtractor(
                allow=r"m\.111\.com\.cn/(?!item/)",
                deny=r"(cart|checkout|account|login|search|city|maps)",
            ),
            follow=True,
        ),
        # Extract product pages (/item/{id}.html)
        Rule(
            LinkExtractor(
                allow=r"/item/\d+\.html",
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
