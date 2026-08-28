"""
Spider for Yandex Market (RU marketplace) — https://market.yandex.ru/.

Search-results pages (`/search?text=<query>&page=N`) are server-rendered and
embed multiple "Apiary" widget-state JSON blobs as
`<noframes data-apiary="patch">{...}</noframes>` -- each one is standalone
valid JSON. The `@marketfront/SearchSchemaOrg` widget carries a clean,
schema.org-shaped item list (sku, name, price, priceCurrency, url,
description) that is the *displayed* price shown to the buyer; a separate
`@light/ToggleWishlist` widget echoes name/price too but its top-level
`price.value` is a stale/pre-discount figure that disagrees with what's
actually rendered (confirmed live 2026-08-07: wishlist widget top-level
price=199 RUB vs. the real displayed/SearchSchemaOrg price=120 RUB for the
same SKU) -- SearchSchemaOrg is the only widget used here.

No plain HTTP JSON API was found (Yandex Market is not Daraz-style); this
walks a fixed keyword list (`_yandex_market_keywords.txt`, mixed food +
non-food COICOP terms) instead, first 3 pages each. Homepage/search carries a
"sleeping" `@marketfront/CaptchaService` widget on every page (standard
boilerplate, not an active challenge) -- kept concurrency at 1 and added a
download delay to avoid waking it.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://market.yandex.ru"
_KEYWORDS_PATH = Path(__file__).parent / "_yandex_market_keywords.txt"
_MAX_PAGES_PER_KEYWORD = 3
_PATCH_RE = re.compile(r'<noframes data-apiary="patch">(.*?)</noframes>', re.DOTALL)


def _load_keywords() -> list[str]:
    return [
        line.strip() for line in _KEYWORDS_PATH.read_text().splitlines() if line.strip()
    ]


def _extract_schema_items(body: str) -> list[dict]:
    items: list[dict] = []
    for raw in _PATCH_RE.findall(body):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        widgets = data.get("widgets") or {}
        for widget_key, widget_val in widgets.items():
            if "SearchSchemaOrg" not in widget_key or not isinstance(widget_val, dict):
                continue
            for payload in widget_val.values():
                if isinstance(payload, dict):
                    items.extend(payload.get("items") or [])
    return items


class YandexMarketSpider(scrapy.Spider):
    name = "yandex_market"
    allowed_domains = ["market.yandex.ru"]
    currency = "RUB"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _search_url(self, keyword: str, page: int) -> str:
        return f"{_BASE}/search?text={quote(keyword)}&page={page}"

    async def start(self):
        for kw in _load_keywords():
            yield scrapy.Request(
                self._search_url(kw, 1),
                callback=self.parse_page,
                meta={"keyword": kw, "page": 1},
            )

    def parse_page(self, response):
        keyword = response.meta["keyword"]
        page = response.meta["page"]
        items = _extract_schema_items(response.text)
        logger.info(f"yandex_market: q={keyword} page={page} count={len(items)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            item = self._item(it, keyword, scraped_at)
            if item:
                yield item
        if items and page < _MAX_PAGES_PER_KEYWORD:
            nxt = page + 1
            yield scrapy.Request(
                self._search_url(keyword, nxt),
                callback=self.parse_page,
                meta={"keyword": keyword, "page": nxt},
            )

    def _item(self, it: dict, keyword: str, scraped_at: str):
        name = (it.get("name") or "").strip()
        price = it.get("price")
        sku = it.get("sku")
        url = it.get("url")
        if not name or not price or not sku or not url:
            return None
        return {
            "product_id": str(sku),
            "product_name": html.unescape(name)[:500],
            "category": keyword,
            "price": str(price),
            "currency": it.get("priceCurrency") or self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
