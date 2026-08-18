"""asaxiy.uz -- Uzbekistan general retailer (electronics/appliances/books/
household), custom platform (COICOP: mixed, dept-store-like).

Verified live 2026-08-17: curl_cffi impersonate=chrome124 clears cleanly
(bare curl got Cloudflare "Attention Required"; chrome120/safari17_0 also
clear). robots.txt explicitly Allows GPTBot/ClaudeBot/anthropic-ai/etc. on
the main path.

The earlier probe only sampled the homepage's "discount rail" (curated,
unpaginated). The real catalog lives under ``/uz/product/<category-path>``
-- e.g. ``/uz/product/telefony-i-gadzhety/telefony/smartfony`` -- discovered
live from real homepage links (Russian-locale variants under ``/ru/product/``
confirmed the same category slugs exist under ``/uz/product/``).

Each category page embeds a clean JSON-LD ItemList (24 entries: name, url)
via ``<script type="application/ld+json">`` with ``@type: ItemList`` -- but
that block carries no price. Price lives in the HTML tiles as
``<span class="product__item-price product-main-price-id-<id>">5 339 000
so'm</span>`` (space-grouped UZS, no decimals). The ItemList entries and the
price spans appear in the same document order (verified live: both lists
are length-24 and index-i pairs match by product), so this spider zips them
by position rather than re-deriving a numeric id from the ItemList (which
has none).

Enumerability verified live: the smartphones category (page 1, no param)
and ...?page=2 each returned 24 distinct product URLs, ZERO overlap.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ITEMLIST_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)
_PRICE_RE = re.compile(r"product-main-price-id-(\d+)\">([\d\s]+) so'm")

_CATEGORIES = (
    "telefony-i-gadzhety/telefony/smartfony",
    "klimaticheskaya-tehnika/kondicionery",
    "knigi",
    "kompyutery-i-orgtehnika",
    "posuda",
    "telefony-i-gadzhety",
    "televizory-video-i-audio",
    "bytovaya-tehnika/texniki-dlya-krasota-i-zdorove",
    "dlya-gejmerov",
    "sport-i-otdyh/bassejny",
)

MAX_PAGES = 25


class AsaxiyUzSpider(scrapy.Spider):
    name = "asaxiy_uz"
    allowed_domains = ["asaxiy.uz"]
    currency = "UZS"
    language = "uz"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"https://asaxiy.uz/uz/product/{slug}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        names_urls = self._extract_item_list(response.text)
        prices = _PRICE_RE.findall(response.text)
        n = min(len(names_urls), len(prices))
        logger.info(
            f"asaxiy_uz: {slug} page={page} names={len(names_urls)} prices={len(prices)}"
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for i in range(n):
            name, url = names_urls[i]
            product_id, price_raw = prices[i]
            item = self._parse_item(product_id, name, url, price_raw, scraped_at)
            if item is not None:
                yield item

        if n > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"https://asaxiy.uz/uz/product/{slug}?page={nxt}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": nxt},
            )

    def _extract_item_list(self, body: str) -> list:
        for block in _ITEMLIST_RE.findall(body):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                return [
                    (entry.get("name"), entry.get("url"))
                    for entry in data.get("itemListElement", [])
                    if entry.get("name") and entry.get("url")
                ]
        return []

    def _parse_item(
        self, product_id: str, name: str, url: str, price_raw: str, scraped_at: str
    ) -> dict | None:
        try:
            price = float(price_raw.replace(" ", "").replace("\xa0", ""))
        except ValueError:
            return None

        category = url.rsplit("/", 1)[-1].replace("-", " ")

        return {
            "product_id": product_id,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
