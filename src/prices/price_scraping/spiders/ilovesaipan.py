"""
Spider for I Love Saipan Online Store (Northern Mariana Islands) - https://shop.ilovesaipan.net/
Odoo eCommerce storefront (server: Odoo.sh). Extracts product information
including prices, categories, and URLs.
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
import logging

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class IloveSaipanSpider(CrawlSpider):
    """
    CrawlSpider for I Love Saipan Online Store (Odoo shop).
    Discovers category listing pages, follows pagination, and extracts
    product data from Odoo product detail pages.
    """

    name = "ilovesaipan"
    allowed_domains = ["shop.ilovesaipan.net"]
    start_urls = [
        "https://shop.ilovesaipan.net/shop/category/grocery-262",
        "https://shop.ilovesaipan.net/shop/category/beauty-hygiene-258",
        "https://shop.ilovesaipan.net/shop/category/fashion-accessories-257",
        "https://shop.ilovesaipan.net/shop/category/house-essentials-260",
        "https://shop.ilovesaipan.net/shop/category/kitchen-appliances-supplies-263",
        "https://shop.ilovesaipan.net/shop/category/pets-261",
        "https://shop.ilovesaipan.net/shop/category/school-office-supplies-259",
        "https://shop.ilovesaipan.net/shop/category/souvenirs-240",
    ]
    currency = "USD"

    SELECTORS = get_selectors("ilovesaipan")

    rules = (
        # Follow pagination within a category
        Rule(
            LinkExtractor(
                allow=r"/shop/category/[a-z0-9\-]+/page/\d+",
            ),
            follow=True,
        ),
        # Extract product pages (Odoo pattern: /shop/{slug}-{id})
        Rule(
            LinkExtractor(
                allow=r"/shop/[a-z0-9\-]+-\d+",
                deny=r"(cart|checkout|account|login|search|wishlist|/shop/category/)",
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
        product_id = extractor.extract("product_id", self.SELECTORS["product_id"])

        if product_name and price:
            yield {
                "product_id": product_id,
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
