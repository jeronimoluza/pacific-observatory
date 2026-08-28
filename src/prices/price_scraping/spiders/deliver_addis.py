"""
Spider for Deliver Addis - Market (Ethiopia) — https://deliveraddis.com/market.

Server-rendered category pages (custom delivery-app stack). The market's own
nav exposes a fixed set of `/market/<category>` pages (and two nested
`/market/<category>/<subcategory>` pages); each renders its full product
grid directly in the HTML — no `?page=` pagination observed. Product cards
follow a stable shape:
`<input type="hidden" value="ID" name="product" /><a class="product-card"
href="URL">...product-name montserrat">NAME</div>...<p class="price">
PRICE ETB</p>`.

Re-verified live 2026-08-06: GET /market -> 200, 47KB, real ETB prices
('550.00 ETB', '1,200.00 ETB'). GET /market/coffee -> 200, 8 real product
cards incl. 'Galani Coffee - House Blend' 890.00 ETB. The aggregate
`/market/full` overview page also SSRs (200, 80KB, 56 product cards) but
some of its per-category sections are truncated behind a JS "load more"
button (POST /GetMore) that we don't follow here — walking every named
category page directly gives fuller, simpler coverage without that
complexity.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://deliveraddis.com"
_CATEGORY_PATHS = [
    "/market/belvedere-home-made-shop-products",
    "/market/canned-and-bottled-foods",
    "/market/coffee",
    "/market/fc-red-meat",
    "/market/fc-red-meat/leg-cut-of-sheep",
    "/market/galani-bundles",
    "/market/gift-boxes",
    "/market/honey",
    "/market/liyu-injera",
    "/market/sabae-coffee",
    "/market/sabae-coffee/sabae-coffee-empower",
    "/market/sabae-coffee/sabae-coffee-motivate",
    "/market/sauce",
    "/market/zede-instant-foods",
]
_CARD_RE = re.compile(
    r'<input type="hidden" value="(\d+)" name="product" />\s*'
    r'<a class="product-card" href="([^"]+)">.*?'
    r'product-name montserrat">\s*([^<]+?)\s*</div>.*?'
    r'<p class="price">([\d,]+\.\d{2}) ETB</p>',
    re.S,
)

# Archived-page-only: a captured URL under /market/<category>/<slug> is a
# single-product detail page (a different template from the /market/<category>
# listing pages the live crawl walks), whose `og:title` meta is polluted with
# a "Deliver Addis - Market - " site-name prefix (confirmed live 2026-08-18,
# so the shared meta tier is skipped for this spider) and has no price meta
# at all. The real name/price sit in plain markup instead:
# `<input type="hidden" value="ID" name="product" /><h1 class="title">NAME
# </h1><h3 data-base-price="PRICE" class="price">`.
_PDP_RE = re.compile(
    r'<input type="hidden" value="(\d+)" name="product" />\s*'
    r'<h1 class="title">\s*([^<]+?)\s*</h1>\s*'
    r'<h3 data-base-price="([\d.]+)" class="price">',
    re.S,
)


class DeliverAddisSpider(scrapy.Spider):
    name = "deliver_addis"
    allowed_domains = ["deliveraddis.com"]
    currency = "ETB"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for path in _CATEGORY_PATHS:
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_category,
                meta={"category_path": path},
            )

    def parse_category(self, response):
        category = response.meta["category_path"].split("/market/", 1)[-1]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"deliver_addis: {category} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, url_path, name, price in cards:
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": category.replace("/", " > "),
                "price": price.replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Archived
    # snapshots can be either page type this spider itself produces urls
    # for -- a category listing (`_CARD_RE`, one row per card, same as live)
    # or a single-product detail page (`_PDP_RE`, see its comment). Neither
    # carries JSON-LD; the shared meta tier is skipped (og:title here is
    # site-name-prefixed, not the clean product name).
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Deliver Addis page (category listing or PDP)."""
        cards = _CARD_RE.findall(html_text)
        if cards:
            for product_id, url_path, name, price in cards:
                yield {
                    "product_id": product_id,
                    "product_name": name.strip()[:500],
                    "price": price.replace(",", ""),
                    "currency": cls.currency,
                    "available": True,
                    "url": f"{_BASE}{url_path}",
                    "language": cls.language,
                }
            return

        m = _PDP_RE.search(html_text)
        if not m:
            return
        product_id, name, price = m.groups()
        yield {
            "product_id": product_id,
            "product_name": name.strip()[:500],
            "price": price,
            "currency": cls.currency,
            "available": True,
            "url": url,
            "language": cls.language,
        }
