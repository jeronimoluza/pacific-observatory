"""
Spider for Daraz Pakistan (marketplace) — https://www.daraz.pk/.

A Lazada-derived marketplace, same platform family as `daraz_np` (Nepal).
The catalog-search AJAX surface is unauthenticated and unsigned:
GET /catalog/?ajax=true&isFirstRequest=true&page=N&q=<keyword> -> 200,
plain JSON, mods.listItems = up to 40 products/page with name, price,
originalPrice, discount, sellerName, itemUrl. Verified live 2026-09-10:
q=rice page=1 -> 40 items, page=2 -> 40 items, 0 itemId overlap (confirmed
distinct), e.g. "Poha / Flattened Rice / White Poha Rice - 100g" Rs. 171,
"Falak Bachat 5 Kg" Rs. 1,487. `price` has no currency field in the JSON
payload -- the site's own display string is "Rs. <amount>" (Pakistani
rupee), so currency is hardcoded PKR at the spider level rather than
parsed from the site (never derive currency from a displayed symbol).

The original probe for this batch found only 60 product URLs via a
sitemap-style pattern, which the batch brief flagged as certainly an
undercount for a marketplace this size -- confirmed: the search AJAX
surface alone returns 40 distinct products per keyword per page with no
sign of exhausting supply. Reuses `daraz_np`'s keyword-walk strategy
(same `_daraz_np_keywords.txt` list, food/staple terms, since no single
category crawl reaches deep leaf breadth on this marketplace either) —
copied to `_daraz_pk_keywords.txt` per-country per repo convention, 3
pages/keyword cap (120 items/keyword).
"""

import html
import logging
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.daraz.pk"
_KEYWORDS_PATH = Path(__file__).parent / "_daraz_pk_keywords.txt"
_MAX_PAGES_PER_KEYWORD = 3


def _load_keywords() -> list[str]:
    return [
        line.strip() for line in _KEYWORDS_PATH.read_text().splitlines() if line.strip()
    ]


class DarazPkSpider(scrapy.Spider):
    name = "daraz_pk"
    allowed_domains = ["daraz.pk"]
    currency = "PKR"
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
            logger.warning(f"daraz_pk: non-JSON response for q={keyword} page={page}")
            return
        items = (data.get("mods") or {}).get("listItems") or []
        logger.info(f"daraz_pk: q={keyword} page={page} count={len(items)}")
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
