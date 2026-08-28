"""
Spider for drluxe.ir -- "Dr Luxe" Iranian online pharmacy (Tehran).

داروخانه آنلاین دکتر لوکس -- sells supplements, baby/personal-care and
cosmetics products, IRR pricing. No JSON API found; the product sitemap
(https://drluxe.ir/sitemap/products, paginated ?page=2..9, ~9k URLs) is
the walkable catalog. PDPs carry no schema.org JSON-LD; price/name come
from OpenGraph/product meta tags instead. Confirmed live 2026-08-18:
"عصاره خوری کودک مناسب بالای 6 ماه بی بی لند کد 285" -> IRR 4,047,000
(meta method, matches the pre-verified candidate-list sample).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from price_scraping.archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://drluxe.ir/sitemap.xml"
_PRODUCT_SITEMAP_RE = re.compile(
    r"<loc>(https://drluxe\.ir/sitemap/products(?:\?page=\d+)?)</loc>"
)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


class DrluxeIrSpider(scrapy.Spider):
    name = "drluxe_ir"
    allowed_domains = ["drluxe.ir"]
    currency = "IRR"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_index)

    def parse_index(self, response):
        for loc in _PRODUCT_SITEMAP_RE.findall(response.text):
            yield scrapy.Request(loc, callback=self.parse_product_sitemap)

    def parse_product_sitemap(self, response):
        urls = sorted(set(_LOC_RE.findall(response.text)))
        logger.info(f"drluxe_ir: {len(urls)} product URLs in {response.url}")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        rows = rows_from_jsonld(response.text, response.url)
        if not rows:
            one = row_from_meta(response.text, response.url)
            rows = [one] if one else []
        for row in rows:
            row.setdefault("currency", self.currency)
            row["language"] = self.language
            row["scraped_at_utc"] = datetime.now(timezone.utc).isoformat()
            yield row
