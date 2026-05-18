"""
Spider for Tata 1mg (India pharmacy) - https://www.1mg.com/

CrawlSpider Pattern A — PDPs at /otc/<slug>-otc<id> and /drugs/<slug>-<id>.
Extracts product data from the JSON-LD script tag (Product / Drug @type).
CSS-class selectors are unusable because prices are React-hydrated and
the SSR HTML has empty price elements.
"""

import json
import logging
import re

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)

JSONLD_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL,
)


class Tata1mgSpider(CrawlSpider):
    name = "tata_1mg"
    allowed_domains = ["www.1mg.com", "1mg.com"]
    start_urls = [
        "https://www.1mg.com/categories/vitamins-nutrition-5",
        "https://www.1mg.com/categories/diabetes-care-21",
        "https://www.1mg.com/categories/personal-care-30",
        "https://www.1mg.com/drugs-all-medicines",
    ]
    currency = "INR"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/(otc|drugs)/[a-z0-9\-]+(otc|-)\d+$",
                deny=r"(cart|checkout|login|search|/labs/|/doctors|/appointment|/blog|/articles|/categories/)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        for match in JSONLD_RE.finditer(response.text):
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("@type") not in ("Product", "Drug"):
                continue
            offers = data.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price")
            name = data.get("name")
            if not name or price is None:
                continue
            yield {
                "product_id": data.get("sku") or data.get("productID"),
                "product_name": name,
                "price": price,
                "currency": offers.get("priceCurrency") or self.currency,
                "category": None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            return
        logger.warning(f"No JSON-LD Product/Drug found at {response.url}")
