"""
Spider for hoshmandshop.ir -- "Hoshmand Shop" Iranian cosmetics/perfume
store. هوشمند شاپ.

No JSON API found; walks the sitemap index
(https://hoshmandshop.ir/sitemap.xml) -> one product sub-sitemap per
month (.../sitemap.xml/products/YYYY-MM), each carrying real /product/
<slug> URLs. PDPs embed a clean schema.org Product JSON-LD block.
Confirmed live 2026-08-18: "Layton مشابه بو مارلی لیتون" -> IRR
29,429,400 (jsonld method, matches the pre-verified candidate-list
sample: bou marley layton clone perfume).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from price_scraping.archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://hoshmandshop.ir/sitemap.xml"
_PRODUCT_SITEMAP_RE = re.compile(
    r"<loc>(https://hoshmandshop\.ir/sitemap\.xml/products/[^<]+)</loc>"
)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


class HoshmandshopIrSpider(scrapy.Spider):
    name = "hoshmandshop_ir"
    allowed_domains = ["hoshmandshop.ir"]
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
        logger.info(f"hoshmandshop_ir: {len(urls)} product URLs in {response.url}")
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
