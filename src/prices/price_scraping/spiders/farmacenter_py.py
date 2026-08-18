"""
Farmacenter (Paraguay) - https://www.farmacenter.com.py

Homepage/category HTML is a client-rendered shell with no price tokens, but
individual product pages ARE server-rendered with full schema.org Product +
Offer microdata (itemprop="price"/"priceCurrency"). No impersonation
needed - plain requests clear both the sitemap and product pages.

robots.txt points at /sitemap; the actual product-URL sitemap is
/sitemap/catalogo-articulos.xml (10,080 URLs, confirmed live 2026-08-17) -
this single file is the whole enumerable product universe, not a curated
subset. Prices are PYG, confirmed directly from each product's own
itemprop="priceCurrency" content.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.farmacenter.com.py/sitemap/catalogo-articulos.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NAME_RE = re.compile(r'itemprop="name">([^<]+)</span>')
_PRICE_RE = re.compile(r'itemprop="price" content="([^"]+)"')
_CURRENCY_RE = re.compile(r'itemprop="priceCurrency" content="([^"]+)"')


class FarmacenterPySpider(scrapy.Spider):
    name = "farmacenter_py"
    allowed_domains = ["farmacenter.com.py"]
    currency = "PYG"
    language = "es"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info("farmacenter_py: %s product urls in sitemap", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        name_m = _NAME_RE.search(response.text)
        price_m = _PRICE_RE.search(response.text)
        if not name_m or not price_m:
            return
        currency_m = _CURRENCY_RE.search(response.text)
        product_id = response.url.rstrip("/").rsplit("_", 1)[-1]
        yield {
            "product_id": product_id,
            "product_name": name_m.group(1).strip()[:500],
            "category": None,
            "price": price_m.group(1),
            "currency": (currency_m.group(1) if currency_m else self.currency),
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
