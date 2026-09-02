"""
Spider for Mekina (Ethiopia) — https://www.mekina.net/

Dedicated used/new car marketplace for Ethiopia (Next.js app; the
`/cars/search` listing page is client-rendered with no server-side product
JSON, so this spider does not crawl it). Mekina publishes five RSS feeds
that ARE fully server-rendered XML with a structured, non-standard
`<price>` element already carrying the currency suffix (e.g.
"5,450,000 ETB"): `/feed` (latest), `/feed/featured`, `/feed/private`,
`/feed/brokers`, `/feed/dealers`. Each feed caps at 20 `<item>` entries, but
the five feeds only partially overlap — re-verified live 2026-09-01: 100
raw `<item>` entries (5 x 20) collapse to 75 distinct `<guid>` values.

The feed mixes brand-new and used vehicles under a shared `<category>`
tag (e.g. "Brand new"/"Vehicle" vs "Used"/"Vehicle") — no narrow COICOP
short-circuit is declared in the YAML for this reason (coicop_classification:
classifier, matching tayara_tn's general-classifieds pattern rather than
pakwheels_pk's used-only narrow one).

A minority of listings carry `<price>Price on request</price>` (no numeric
value, seller declined to list a price) instead of a real amount — these
are dropped rather than shipped as a fabricated 0/None price.

No PDP crawl is needed: every field the item schema wants (name, price,
currency, category, url, a stable id) is already in the feed itself. The
`<guid>` is the same slug/id suffix used in the listing's own URL.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_FEED_URLS = [
    "https://www.mekina.net/feed",
    "https://www.mekina.net/feed/featured",
    "https://www.mekina.net/feed/private",
    "https://www.mekina.net/feed/brokers",
    "https://www.mekina.net/feed/dealers",
]
_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
_TITLE_RE = re.compile(r"<title><!\[CDATA\[(.*?)\]\]></title>")
_LINK_RE = re.compile(r"<link>(.*?)</link>")
_GUID_RE = re.compile(
    r"<guid[^>]*><!\[CDATA\[(.*?)\]\]></guid>|<guid[^>]*>(.*?)</guid>"
)
_CATEGORY_RE = re.compile(r"<category><!\[CDATA\[(.*?)\]\]></category>")
_PRICE_RE = re.compile(r"<price>([\d,]+)\s*([A-Z]{3})</price>")


class MekinaEtSpider(scrapy.Spider):
    name = "mekina_et"
    allowed_domains = ["www.mekina.net", "mekina.net"]
    currency = "ETB"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    async def start(self):
        for url in _FEED_URLS:
            yield scrapy.Request(url, callback=self.parse_feed)

    def parse_feed(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        blocks = _ITEM_RE.findall(response.text)
        logger.info(f"mekina_et: {response.url} -> {len(blocks)} raw items")
        for block in blocks:
            title_m = _TITLE_RE.search(block)
            link_m = _LINK_RE.search(block)
            guid_m = _GUID_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not (title_m and link_m and guid_m and price_m):
                continue  # e.g. "Price on request" listings with no numeric price
            product_id = guid_m.group(1) or guid_m.group(2)
            if product_id in self.seen_ids:
                continue
            self.seen_ids.add(product_id)
            categories = _CATEGORY_RE.findall(block)
            yield {
                "product_id": product_id,
                "product_name": title_m.group(1).strip()[:500],
                "category": ", ".join(categories) if categories else None,
                "price": price_m.group(1).replace(",", ""),
                "currency": price_m.group(2) or self.currency,
                "available": True,
                "url": link_m.group(1).strip(),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
