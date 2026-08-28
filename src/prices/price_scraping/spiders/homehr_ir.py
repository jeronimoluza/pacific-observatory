"""
Spider for homehr.ir -- "HomeHR" Iranian cosmetics/personal-care store
(Mashhad). فروشگاه اینترنتی هومهر.

No JSON API found; walks the WordPress-style sitemap index
(https://homehr.ir/sitemap.xml) -> product-sitemap1..5.xml (~2k URLs
each, ~10k total). PDPs carry no schema.org JSON-LD; price/name come
from OpenGraph/product meta tags. Confirmed live 2026-08-18:
"سرم تقویت کننده ابرو اکسیلیا" -> IRR 1,186,000 (meta method, matches
the pre-verified candidate-list sample).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from price_scraping.archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://homehr.ir/sitemap.xml"
_PRODUCT_SITEMAP_RE = re.compile(
    r"<loc>(https://homehr\.ir/product-sitemap\d+\.xml)</loc>"
)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


class HomehrIrSpider(scrapy.Spider):
    name = "homehr_ir"
    allowed_domains = ["homehr.ir"]
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
        logger.info(f"homehr_ir: {len(urls)} product URLs in {response.url}")
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
