"""
Spider for Pevex — https://www.pevex.hr/ (Croatian hardware/home-improvement
and electronics/appliance chain).

Custom .NET-style storefront (server: "storefront-security-hardening" meta,
no Next.js/Nuxt marker). Category listing pages (e.g.
/elektronika/mobiteli-i-satovi/mobiteli) server-render up to 20 product
cards directly in HTML: name + URL slug (`a.product-display-grid-image`
href/title), numeric id (`data-product-id`), brand (`data-product-brand`),
and price (`.price-value`). No pagination mechanism was found in the static
HTML (no `?index=`/`?page_size=` params changed the result set in testing,
and no load-more endpoint was discoverable without a browser) so this
spider takes the first ~20 products per leaf category -- still a real,
non-trivial catalogue across 400 categories.

Verified live 2026-09-06: GET /elektronika/mobiteli-i-satovi/mobiteli -> 200,
20 products, e.g. "Mobitel Samsung Galaxy A27 5 g 6,7",6GB, 128GB, crni"
id=106408 EUR 349.90.

Category list (400 leaf slugs, `_pevex_hr_categories.txt`) seeded from
https://www.pevex.hr/xml/sitemap_3_1.xml + sitemap_3_2.xml: collected all
distinct base paths (query string stripped) that carry a filter query
string (`?f=1&index=1&brand=...`), then kept only leaf paths (no other
collected path is a strict sub-path of it).
"""

import logging
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.pevex.hr"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_pevex_hr_categories.txt"

_ITEM_SPLIT = 'class="product-list-item-outer"'
_NAME_RE = re.compile(r'product-display-grid-image"\s+href="([^"]+)"\s+title="([^"]+)"')
_BRAND_RE = re.compile(r'data-product-brand="([^"]*)"')
_PID_RE = re.compile(r'data-product-id="(\d+)"')
_PRICE_RE = re.compile(r'price-value">\s*([\d.,]+)\s*<span class="currency">([^<]*)</span>')


def _load_categories():
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class PevexHrSpider(scrapy.Spider):
    name = "pevex_hr"
    allowed_domains = ["pevex.hr"]
    currency = "EUR"
    language = "hr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 30,
    }

    async def start(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}{slug}",
                callback=self.parse_page,
                meta={"slug": slug},
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        blocks = response.text.split(_ITEM_SPLIT)[1:]
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for block in blocks:
            name_m = _NAME_RE.search(block)
            pid_m = _PID_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not (name_m and pid_m and price_m):
                continue
            url_path, name = name_m.groups()
            brand_m = _BRAND_RE.search(block)
            price = price_m.group(1).replace(".", "").replace(",", ".")
            count += 1
            yield {
                "product_id": pid_m.group(1),
                "product_name": unescape(name).strip()[:500],
                "brand": brand_m.group(1) if brand_m else None,
                "category": slug.strip("/"),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"pevex_hr: {slug} items={count}")
