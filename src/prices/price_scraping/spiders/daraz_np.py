"""
Spider for Daraz Nepal (marketplace) — https://www.daraz.com.np/.

A Lazada-derived marketplace. The catalog-search AJAX surface is
unauthenticated and unsigned (unlike Daraz's `mtop` product-detail API):
GET /catalog/?ajax=true&isFirstRequest=true&page=N&q=<keyword> -> 200,
plain JSON, `mods.listItems` = up to 40 products/page with name, price,
originalPrice, discount, sellerName, itemUrl. Re-verified live 2026-08-06:
q=rice page=1 -> 40 items incl. 'Hilife Pulao Basmati Rice 1 Kg' Rs 264,
'Local Kalanamak Rice 1 Kg' Rs 320.

No single category crawl reaches deep leaf breadth on this marketplace (per
round 1), so this walks a fixed keyword list
(`_daraz_np_keywords.txt`, food/staple terms) instead, one query per
keyword, first 3 pages each (120 items/keyword cap) — flash-sale price
volatility is a known caveat (originalPrice/discount fields retained
implicitly via `price`, which is already the current/sale price shown to
a buyer).
"""

import html
import logging
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.daraz.com.np"
_KEYWORDS_PATH = Path(__file__).parent / "_daraz_np_keywords.txt"
_MAX_PAGES_PER_KEYWORD = 3


def _load_keywords() -> list[str]:
    return [
        line.strip() for line in _KEYWORDS_PATH.read_text().splitlines() if line.strip()
    ]


class DarazNpSpider(scrapy.Spider):
    name = "daraz_np"
    allowed_domains = ["daraz.com.np"]
    currency = "NPR"
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

    def _search_url(self, keyword: str, page: int) -> str:
        return (
            f"{_BASE}/catalog/?ajax=true&isFirstRequest=true"
            f"&page={page}&q={keyword.replace(' ', '+')}"
        )

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
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"daraz_np: non-JSON response for q={keyword} page={page}")
            return
        items = (data.get("mods") or {}).get("listItems") or []
        logger.info(f"daraz_np: q={keyword} page={page} count={len(items)}")
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
        item_id = it.get("itemId") or it.get("nid")
        if not name or not price or not item_id:
            return None
        item_url = it.get("itemUrl") or ""
        if item_url.startswith("//"):
            item_url = f"https:{item_url}"
        elif item_url and not item_url.startswith("http"):
            item_url = f"{_BASE}{item_url}"
        return {
            "product_id": str(item_id),
            "product_name": html.unescape(name)[:500],
            "category": keyword,
            "price": str(price),
            "currency": self.currency,
            "available": bool(it.get("inStock", True)),
            "url": item_url or f"{_BASE}/products/i{item_id}.html",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
