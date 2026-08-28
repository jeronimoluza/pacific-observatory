"""
Spider for golsima.com -- "Golsima" Iranian K-beauty cosmetics store,
IRR pricing despite the .com TLD. فروشگاه آنلاین گلسیما.

Next.js storefront; category/brand pages are the only entries in
https://golsima.com/sitemap.xml (products aren't listed there), so this
walks each category/brand page from the sitemap and picks up product
links rendered inline on it -- any single-segment path whose first
segment isn't one of the known category/utility roots. PDPs embed a
clean schema.org Product JSON-LD block. Confirmed live 2026-08-18:
"کرم مرطوب کننده ۵ سراماید برنج سیاه هاروهارو وان" -> IRR 31,990,000
(jsonld method, matches the pre-verified candidate-list sample).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from price_scraping.archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_SITEMAP = "https://golsima.com/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LINK_RE = re.compile(r'href="(/[a-z0-9\-]+/)"')
_NON_PRODUCT_ROOTS = {
    "makeup",
    "body",
    "skincare",
    "hair",
    "brand",
    "about",
    "account",
    "club",
    "contact",
    "terms",
    "products",
}


class GolsimaIrSpider(scrapy.Spider):
    name = "golsima_ir"
    allowed_domains = ["golsima.com"]
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
        listing_urls = []
        for loc in _LOC_RE.findall(response.text):
            path = loc.replace("https://golsima.com", "")
            root = path.strip("/").split("/")[0] if path.strip("/") else ""
            if root in {"", "products", "club", "contact", "terms", "about", "account"}:
                continue
            listing_urls.append(loc)
        logger.info(f"golsima_ir: {len(listing_urls)} category/brand listing pages")
        for url in listing_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        product_paths = set()
        for path in _LINK_RE.findall(response.text):
            root = path.strip("/").split("/")[0]
            if root not in _NON_PRODUCT_ROOTS:
                product_paths.add(path)
        for path in sorted(product_paths):
            yield scrapy.Request(response.urljoin(path), callback=self.parse_product)

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
