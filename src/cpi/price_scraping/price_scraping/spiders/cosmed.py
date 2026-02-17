"""
Spider for scraping Cosmed (Taiwan) - https://shop.cosmed.com.tw/
Extracts product information including prices, categories, and URLs.

Cosmed uses an Angular SPA with JSON data embedded in raw HTML.
Product pages are at /SalePage/Index/{id} and contain JSON with
"Title", "Price", and "CategoryName" fields.
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging
import re

logger = logging.getLogger(__name__)


class CosmedSpider(CrawlSpider):
    """
    CrawlSpider for Cosmed (Taiwan).
    Discovers product pages via SalePage links and extracts price data
    from embedded JSON in the HTML.
    """

    name = "cosmed"
    allowed_domains = ["shop.cosmed.com.tw"]
    start_urls = [
        "https://shop.cosmed.com.tw/",
    ]
    country = "taiwan"
    currency = "TWD"

    rules = (
        # Follow SalePage product links
        Rule(
            LinkExtractor(
                allow=r"/SalePage/Index/\d+",
                deny=r"(cart|checkout|account|login|search|ShoppingCart|TradesOrder|VipMember|ECoupon|GameModule)",
            ),
            callback="parse_product",
            follow=True,
        ),
        # Follow category/listing links
        Rule(
            LinkExtractor(
                allow=r"/TraceSalePageList/",
                deny=r"(cart|checkout|account|login|search)",
            ),
            follow=True,
        ),
    )

    def parse_product(self, response):
        """Parse product page and extract data from embedded JSON."""
        # Extract Title from JSON in HTML
        title_match = re.search(r'"Title"\s*:\s*"([^"]+)"', response.text)
        price_match = re.search(r'"Price"\s*:\s*([\d.]+)', response.text)
        category_match = re.search(r'"CategoryName"\s*:\s*"([^"]+)"', response.text)

        product_name = title_match.group(1) if title_match else None
        price = price_match.group(1) if price_match else None
        category = category_match.group(1) if category_match else None

        # Skip placeholder titles
        if product_name and product_name in ("-1", "null", ""):
            product_name = None

        if product_name and price:
            yield {
                "product_name": product_name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")
