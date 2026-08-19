"""
Spider for irajgallery.ir -- "Iraj Gallery" Iranian cosmetics/hair-dye
store, 20+ years in business. ایرج گالری.

No JSON API found; the single sitemap (https://irajgallery.ir/sitemap.xml,
~650KB) mixes category pages (/shop/<id>-<category-slug>/) with real
product-detail pages (/shop/<category>/P<id>-<slug>.html) -- filtered on
the /P<digits>- marker. PDPs embed a clean schema.org Product JSON-LD
block. Confirmed live 2026-08-18: "مام ژله‌ای سکرت بدون عطر ۴۸ ساعته"
(Secret deodorant gel) -> IRR 11,000,000 (jsonld method).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from price_scraping.archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_SITEMAP = "https://irajgallery.ir/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRODUCT_URL_RE = re.compile(r"/P\d+-")


class IrajgalleryIrSpider(scrapy.Spider):
    name = "irajgallery_ir"
    allowed_domains = ["irajgallery.ir"]
    currency = "IRR"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = sorted(
            {u for u in _LOC_RE.findall(response.text) if _PRODUCT_URL_RE.search(u)}
        )
        logger.info(f"irajgallery_ir: {len(urls)} product URLs in {response.url}")
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
