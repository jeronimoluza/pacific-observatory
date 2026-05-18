"""
Spider for Singer Sri Lanka - https://www.singersl.com/

CrawlSpider. PDPs are at /product/<slug> (singular).
Listing/category pages are at /products/<cat>/<sub>/<subsub>.
JSON-LD has clean Product with offers[].price + priceCurrency.
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


class SingerLkSpider(CrawlSpider):
    name = "singer_lk"
    allowed_domains = ["www.singersl.com", "singersl.com"]
    start_urls = [
        "https://www.singersl.com/products",
        "https://www.singersl.com/products/electronics",
        "https://www.singersl.com/products/home-appliances",
        "https://www.singersl.com/products/kitchen-appliances",
        "https://www.singersl.com/products/appliances",
        "https://www.singersl.com/products/furniture",
        "https://www.singersl.com/products/entertainment",
        "https://www.singersl.com/products/personal-care-and-fitness-equipment",
        "https://www.singersl.com/products/sewing-machines",
        "https://www.singersl.com/products/agro-products",
        "https://www.singersl.com/products/baby-care-products",
        "https://www.singersl.com/products/automobile",
        "https://www.singersl.com/products/hardware-items",
        "https://www.singersl.com/products/security-systems",
        "https://www.singersl.com/products/other-products",
    ]
    currency = "LKR"

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=[r"/product/[a-z0-9\-]+$", r"/products/[a-z0-9\-]+(/[a-z0-9\-]+){0,3}$"],
                deny=r"(cart|checkout|login|account|/add/|\?listview|\?page=|\?order_by|json-)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        if "/product/" not in response.url or "/products/" in response.url:
            return
        for match in JSONLD_RE.finditer(response.text):
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("@type") != "Product":
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
        logger.warning(f"No JSON-LD Product found at {response.url}")
