"""
Spider for WHIM (Maldives, Odoo) - https://whim.com.mv/

CrawlSpider Pattern A — Odoo. PDPs at /shop/<slug>-<id>.
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)


class WhimMvSpider(CrawlSpider):
    name = "whim_mv"
    allowed_domains = ["whim.com.mv"]
    start_urls = [
        "https://whim.com.mv/shop/category/baby-child-toys-baby-food-2034",
        "https://whim.com.mv/shop/category/baby-child-toys-baby-care-2036",
        "https://whim.com.mv/shop/category/baby-child-toys-diapering-2035",
        "https://whim.com.mv/shop/category/baby-child-toys-infant-formula-1940",
        "https://whim.com.mv/shop/category/chilled-ham-sausage-2024",
        "https://whim.com.mv/shop/category/dairy-eggs-milk-butter-1942",
        "https://whim.com.mv/shop/category/dairy-eggs-milk-cheese-1943",
        "https://whim.com.mv/shop/category/dairy-eggs-milk-milk-1944",
        "https://whim.com.mv/shop/category/dairy-eggs-milk-yogurt-2033",
        "https://whim.com.mv/shop/category/drinks-chocolate-malted-1946",
        "https://whim.com.mv/shop/category/drinks-coffee-1947",
        "https://whim.com.mv/shop/category/drinks-cordials-1948",
        "https://whim.com.mv/shop/category/drinks-juices-1949",
        "https://whim.com.mv/shop/category/drinks-soft-drinks-1951",
        "https://whim.com.mv/shop/category/drinks-tea-1952",
        "https://whim.com.mv/shop/category/drinks-water-1953",
        "https://whim.com.mv/shop/category/fresh-fruits-vegetables-1956",
        "https://whim.com.mv/shop/category/frozen-frozen-food-1959",
    ]
    # Follow Odoo pagination AND descend into subcategories
    custom_settings = {
        "DEPTH_LIMIT": 5,
    }
    currency = "MVR"

    SELECTORS = {
        "product_name": [
            "h1[itemprop='name'] span.text-break::text",
            "h1.product_name::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "h5.oe_price span.oe_currency_value::text",
            "span.oe_price span.oe_currency_value::text",
            "span[itemprop='price']::attr(content)",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
        ],
        "product_id": [
            "div.product_price span[itemprop='sku']::text",
            "meta[property='product:retailer_item_id']::attr(content)",
        ],
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/shop/[a-z0-9\-]+(/[a-z0-9\-]+)?-\d{4,6}$",
                deny=r"(/cart|/account|/login|/search|/shop/category/|/shop/cart|/shop/checkout)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract("category", self.SELECTORS["category"], method="getall")
        product_id = extractor.extract("product_id", self.SELECTORS["product_id"])

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        else:
            logger.warning(f"Could not extract product data from {response.url}")
