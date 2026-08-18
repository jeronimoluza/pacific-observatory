"""rozetka.com.ua -- Ukraine's largest general marketplace (COICOP: mixed, marketplace).

Verified live 2026-08-17: curl_cffi impersonate=chrome124 clears the Cloudflare
"Just a moment" challenge cleanly (bare curl gets cf-mitigated:challenge).

The site's 15 top-level nav categories (e.g. /ua/bytovaya-himiya/c4429255/)
are empty umbrella hubs -- 0 product tiles server-rendered. Real listings live
one level down: each hub page links out to true leaf categories (e.g.
/ua/sredstva-dlya-stirki/c4625084/, "laundry detergent"). This spider crawls
the 15 hubs once to discover those leaf URLs, then walks each leaf's listing
pages.

Each listing page embeds a clean JSON-LD ItemList
(``<script type="application/ld+json" data-seo="ItemList">``) with 60
Product entries (name, url, offers.price, offers.priceCurrency, offers.
availability) -- no HTML tile parsing needed. Product id is the numeric
segment in the url (``/ua/<id>/p<id>/``).

Enumerability verified live: /ua/sredstva-dlya-stirki/c4625084/ (page 1, no
suffix) returned 76 distinct product ids; .../page=2/ returned 68 distinct
ids with ZERO overlap against page 1.

Pagination is a path segment, not a query string: page N>=2 is
``<category-url>page=<N>/``. A page returning an empty ItemList (or none at
all) ends that category's walk.

The Cloudflare challenge is intermittent even for chrome124 -- retries with
a short delay clear it, so RETRY_TIMES is raised above the project default
and concurrency/delay are kept conservative.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_HUB_RE = re.compile(r'href="(https://rozetka\.com\.ua/ua/[a-z0-9\-]+/c\d+/)"')
_ITEMLIST_RE = re.compile(
    r'<script type="application/ld\+json" data-seo="ItemList"[^>]*>(.*?)</script>',
    re.DOTALL,
)
_PRODUCT_ID_RE = re.compile(r"/p(\d+)/$")

_HUBS = (
    "https://rozetka.com.ua/ua/2577232/c2577232/",
    "https://rozetka.com.ua/ua/alkoholnie-napitki-i-produkty/c4626923/",
    "https://rozetka.com.ua/ua/bytovaya-himiya/c4429255/",
    "https://rozetka.com.ua/ua/computers-notebooks/c80253/",
    "https://rozetka.com.ua/ua/dacha-sad-ogorod/c2394297/",
    "https://rozetka.com.ua/ua/energonezalezhnist/c241576/",
    "https://rozetka.com.ua/ua/game-zone/c80261/",
    "https://rozetka.com.ua/ua/kids/c88468/",
    "https://rozetka.com.ua/ua/krasota-i-zdorovje/c4629305/",
    "https://rozetka.com.ua/ua/office-school-books/c4625734/",
    "https://rozetka.com.ua/ua/podarki-i-tovary-dlya-prazdnikov/c80260/",
    "https://rozetka.com.ua/ua/sport-i-uvlecheniya/c4627893/",
    "https://rozetka.com.ua/ua/telefony-tv-i-ehlektronika/c4627949/",
    "https://rozetka.com.ua/ua/tovary-dlya-doma/c2394287/",
    "https://rozetka.com.ua/ua/zootovary/c3520929/",
)

MAX_PAGES = 40


class RozetkaUaSpider(scrapy.Spider):
    name = "rozetka_ua"
    allowed_domains = ["rozetka.com.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 6,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for hub in _HUBS:
            yield scrapy.Request(hub, callback=self.parse_hub, meta={"hub": hub})

    def parse_hub(self, response):
        hub = response.meta["hub"]
        leaves = sorted(set(_HUB_RE.findall(response.text)) - {hub})
        logger.info(f"rozetka_ua: hub {hub} -> {len(leaves)} leaf categories")
        for leaf in leaves:
            yield scrapy.Request(
                leaf,
                callback=self.parse_listing,
                meta={"category_url": leaf, "page": 1},
            )

    def parse_listing(self, response):
        category_url = response.meta["category_url"]
        page = response.meta["page"]

        items = self._extract_items(response.text)
        logger.info(f"rozetka_ua: {category_url} page={page} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for entry in items:
            item = self._parse_item(entry, scraped_at)
            if item is not None:
                yield item

        if items and page < MAX_PAGES:
            base = category_url.rstrip("/")
            nxt = page + 1
            yield scrapy.Request(
                f"{base}/page={nxt}/",
                callback=self.parse_listing,
                meta={"category_url": category_url, "page": nxt},
            )

    def _extract_items(self, body: str) -> list:
        m = _ITEMLIST_RE.search(body)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning("rozetka_ua: unparseable ItemList JSON-LD")
            return []
        return data.get("itemListElement", [])

    def _parse_item(self, entry: dict, scraped_at: str) -> dict | None:
        product = entry.get("item") or {}
        name = product.get("name")
        url = product.get("url")
        offers = product.get("offers") or {}
        price = offers.get("price")
        if not name or not url or price is None:
            return None

        m = _PRODUCT_ID_RE.search(url)
        product_id = m.group(1) if m else url

        return {
            "product_id": product_id,
            "product_name": str(name)[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": offers.get("availability") == "https://schema.org/InStock",
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
