"""
Spider for Aelan Basket (Vanuatu) - www.aelanbasket.com

Small online supermarket (Port Vila). Server-rendered Next.js PDPs carry
product name, price, and a category breadcrumb directly in the raw HTML
(no JS execution needed) -- Tier 1A. `/shop` is a client-rendered filter
page and yields no links via plain HTTP, so discovery instead crawls from
the homepage (~14 products) and each PDP's "related products" rail, which
surfaces additional SKUs not linked from the homepage.

Prices render as "VT<amount>" (Vatu shorthand for VUV) -- never parse the
symbol; currency is set here at the class level per countries.yaml.

Selectors kept inline per onboarding parallel-safety rules (not registered
in the shared price_scraping/selectors.py).
"""

import logging
import re

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor

logger = logging.getLogger(__name__)

_SELECTORS = {
    "product_name": [
        "h1::text",
    ],
    "price": [
        "span.text-3xl.font-bold::text",
    ],
    "category": [
        "a[href*='/shop?category=']::text",
    ],
}

_LEADING_JUNK_RE = re.compile(r"^[^\w]+")


class AelanbasketVuSpider(CrawlSpider):
    name = "aelanbasket_vu"
    allowed_domains = ["aelanbasket.com"]
    start_urls = ["https://www.aelanbasket.com/"]
    currency = "VUV"
    language = "en"

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/product/[a-zA-Z0-9\-]+$",
                deny=r"(cart|checkout|account|login|wishlist|orders)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", _SELECTORS["product_name"])
        price = extractor.extract("price", _SELECTORS["price"])
        category_parts = extractor.extract(
            "category", _SELECTORS["category"], method="getall"
        )
        product_id = response.url.rstrip("/").rsplit("/", 1)[-1]

        if not (product_name and price):
            logger.warning(f"Could not extract product data from {response.url}")
            return

        category = None
        if category_parts:
            # The breadcrumb anchor's href pattern also matches a duplicate
            # link elsewhere on the page; dedupe text fragments before joining.
            joined = "".join(dict.fromkeys(category_parts)).strip()
            category = _LEADING_JUNK_RE.sub("", joined).strip()

        yield {
            "product_id": product_id,
            "product_name": product_name,
            "price": price.lstrip("VT").replace(",", ""),
            "currency": self.currency,
            "category": category or None,
            "url": response.url,
            "language": self.language,
            "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
        }
        logger.info(f"Scraped product: {product_name}")
