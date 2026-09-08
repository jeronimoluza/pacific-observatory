"""
Spider for Lidl Greece — https://www.lidl-hellas.gr/.

Same ODS/Vue SSR storefront family as lidl_si and lidl_rs: category hub pages
under `/c/<slug>/s<id>` server-render a grid of product tiles, each carrying a
`data-grid-data="{&quot;...&quot;}"` HTML-entity-escaped JSON blob with
title, category and regionsPrices (EUR). Re-verified live 2026-09-06:
/c/fagito-poto/s10068374 -> 200, 524KB, 12 tiles with data-grid-data parsed
cleanly, e.g. "Χαρτί υγείας 3στρώσεων" EUR 3.99, and the weekly-offers page
/c/evdomadiaies-epiloges-26kw37/a10102729 carries the same blob shape.

Category slugs harvested from the homepage nav (`/c/<slug>/s<id>` links);
non-product pages (newsletter signup, GDPR notices, gift cards, Lidl Plus
loyalty program info, imprint) excluded. As with lidl_si, price lives at
regionsPrices.1.currentPrice.price; Lidl-Plus-loyalty-exclusive items fall
back to currentLidlPlusPrice so they aren't dropped.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.lidl-hellas.gr"
_CATEGORIES = [
    "alesto/s10092731",
    "athlitiki-endysi-anapsychi/s10068226",
    "crivit/s10068913",
    "ergaleia-eidi-kipoy/s10068222",
    "fagito-poto/s10068374",
    "galata-galpo/s10065290",
    "galpo/s10065289",
    "giaoyrtia-galpo/s10065302",
    "kainotomia-galpo/s10065307",
    "kitrina-tyria-galpo/s10065293",
    "koyzina-oikiakos-exoplismos/s10068166",
    "leyka-tyria-galpo/s10065291",
    "lupilu/s10050920",
    "mezedes-noma/s10021848",
    "moda-axesoyar/s10068373",
    "noma/s10021676",
    "oikiakos-exoplismos/s10068371",
    "parkside/s10068914",
    "ryzia-ospria-noma/s10021786",
    "silvercrest/s10072577",
    "tyria-noma/s10021736",
    "vrefika-paidika-eidi/s10068225",
    "zymarika-noma/s10021806",
]

_DATA_GRID_RE = re.compile(r'data-grid-data="')


class LidlGrSpider(scrapy.Spider):
    name = "lidl_gr"
    allowed_domains = ["lidl-hellas.gr"]
    currency = "EUR"
    language = "el"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for path in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/c/{path}",
                callback=self.parse_category,
                meta={"category": path.split("/")[0]},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        text = response.text
        n_parsed = 0
        scraped_at = datetime.now(timezone.utc).isoformat()
        for m in _DATA_GRID_RE.finditer(text):
            start = m.end()
            end = text.find('"', start)
            if end == -1:
                continue
            raw = text[start:end]
            try:
                data = json.loads(html.unescape(raw))
            except ValueError:
                continue
            if not isinstance(data, dict) or "itemId" not in data:
                continue
            item = self._item(data, category, scraped_at)
            if item:
                n_parsed += 1
                yield item
        logger.info(f"lidl_gr: {category} items={n_parsed}")

    def _item(self, data: dict, category: str, scraped_at: str):
        region = (data.get("regionsPrices") or {}).get("1") or {}
        price_block = region.get("currentPrice")
        if isinstance(price_block, dict):
            price = price_block.get("price")
        else:
            plus_block = region.get("currentLidlPlusPrice")
            nested = plus_block.get("price") if isinstance(plus_block, dict) else None
            price = nested.get("price") if isinstance(nested, dict) else None
        if not isinstance(price, (int, float)):
            return None
        name = data.get("fullTitle") or data.get("title") or ""
        return {
            "product_id": str(data.get("itemId") or data.get("erpNumber") or ""),
            "product_name": html.unescape(name).strip()[:500],
            "category": data.get("category") or category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(data.get("online", True)),
            "url": f"{_BASE}{data.get('canonicalPath', '')}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
