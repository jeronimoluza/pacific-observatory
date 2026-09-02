"""
Zoomi (Mauritania) — https://zoomiapp.com/.

Multi-vendor food-delivery marketplace ("Royoorders"-branded white-label
platform, a template also seen in other markets — but THIS deployment is
confirmed Mauritania-specific: homepage address "Tevragh Zeina, Nouakchott,
Mauritanie", and the storefront currency switcher is pinned to MRU
(currId=94), not USD/EUR).

The "Supermarchés" top category (/category/supermarches) lists 4 real
grocery/food vendors (probed live 2026-08-31): a full grocery store
("Dream Market"), two butchers and a fishmonger — every vendor under this
category is food, no restaurants. Vendor slugs are discovered from that
category page rather than hardcoded, so a newly onboarded grocery vendor
is picked up automatically.

Each vendor storefront (/vendor/<slug>) is server-rendered HTML (Tier 1A,
no JS needed) with real MRU prices and distinct per-product URLs
(/vendor/<slug>/product/<sku>). Products are grouped into
<section class="scrolling_section" id="..."><h2 class="category-head">
blocks, each containing .product_row cards carrying data-p_sku, an <img
alt="..."> product name, a ".product_price" MRU amount, and the product
page link.

Pagination is a real, cursor-free ?page=N walk that DOES advance (verified
distinct products per page, zero overlap): Dream Market alone returns
263/116/65/38/16 products on pages 1-5 and 0 on page 6 (498 distinct SKUs
total) — the flat page-1 count would have looked like the whole catalog
if pagination weren't walked to exhaustion. Each vendor is walked until an
empty page is returned.

Currency: MRU is current (post-2018 redenomination); no old-MRO evidence
seen (price magnitudes, e.g. "Sel fin extra 750g" 50 MRU, are consistent
with new-ouguiya retail prices, not a 10x-inflated old figure).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://zoomiapp.com"
CATEGORY_URL = f"{BASE_URL}/category/supermarches"
_VENDOR_SLUG_RE = re.compile(r"/vendor/([a-z0-9\-]+)")
_PRICE_RE = re.compile(r"([\d.,]+)\s*MRU")


class ZoomiMrtSpider(scrapy.Spider):
    name = "zoomi_mrt"
    allowed_domains = ["zoomiapp.com"]
    currency = "MRU"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(CATEGORY_URL, callback=self.parse_category)

    def parse_category(self, response):
        slugs = sorted(
            {
                m.group(1)
                for href in response.css("a::attr(href)").getall()
                if (m := _VENDOR_SLUG_RE.search(href))
            }
        )
        logger.info(f"{self.name}: grocery vendors discovered={slugs}")
        for slug in slugs:
            yield self._vendor_request(slug, page=1)

    def _vendor_request(self, slug, page):
        return scrapy.Request(
            f"{BASE_URL}/vendor/{slug}?page={page}",
            callback=self.parse_vendor,
            meta={"slug": slug, "page": page},
            dont_filter=True,
        )

    def parse_vendor(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        rows_total = 0
        for section in response.css("section.scrolling_section"):
            raw_cat = " ".join(section.css("h2.category-head::text").getall())
            category = re.sub(r"\(\d+\).*$", "", raw_cat, flags=re.S).strip()
            category = category or slug
            for row in section.css(".product_row"):
                item = self._item(row, category)
                if item:
                    rows_total += 1
                    yield item

        logger.info(f"{self.name}: vendor={slug} page={page} rows={rows_total}")
        if rows_total > 0:
            yield self._vendor_request(slug, page + 1)

    def _item(self, row, category):
        sku = row.css("::attr(data-p_sku)").get()
        name = row.css("img::attr(alt)").get()
        url = row.css("a::attr(href)").get()
        price_text = " ".join(row.css(".product_price::text").getall())
        m = _PRICE_RE.search(price_text)
        if not sku or not name or not url or not m:
            return None
        price = m.group(1).replace(",", "")
        try:
            price_val = float(price)
        except ValueError:
            return None
        if price_val <= 0:
            return None

        return {
            "product_id": sku,
            "product_name": name.strip()[:500],
            "category": category,
            "price": str(price_val),
            "currency": self.currency,
            "available": True,
            "url": url if url.startswith("http") else f"{BASE_URL}{url}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
