"""
Spider for MPREIS (Austria) — https://www.mpreis.at/.

Custom Vue/Nuxt-style storefront (server-rendered `data-v-*` markup, not a
client-only shell). Category pages embed the *entire* category tree as a
double-JSON-encoded blob in `window.__INITIAL_STATE__ = "...escaped
json..."` -- `shop._categoryById`, keyed by category id, each with
name/productCount/subcategories/pathSegments. Re-verified live 2026-08-06:
root id 38118 ("ProductRoot") has 12,773 products across 332 categories (3
departments: Lebensmittel/Getränke/Drogerie). We fetch one page to harvest
that tree, then walk every LEAF category (no subcategories, productCount>0
-- 236 of them, summing to exactly 12,773).

Pagination is cumulative, not page-by-page: `?currentPage=N` re-renders
pages 1..N concatenated (confirmed: a 92-product leaf showed 48 at N=1 and
the full 92 at N=2). So one request per leaf at a currentPage high enough
to cover its known productCount is sufficient; we still loop with a safety
cap in case productCount is stale.

Product cards: `<a href="/shop/p/<slug>-<id>" class="c3-product ...">` with
nested `<span class="c3-product__producer">BRAND</span>
<span class="c3-product__name">NAME</span>` and
`<span class="c3-product__price-value">PRICE</span>` (EUR, comma decimal).
"""

import html
import json
import logging
import math
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.mpreis.at"
_ROOT_URL = f"{_BASE}/shop/c/lebensmittel-50234186"
_STATE_RE = re.compile(r'window\.__INITIAL_STATE__\s*=\s*"')
_CARD_RE = re.compile(
    r'<a href="(/shop/p/[^"]+)"[^>]*class="c3-product c3-product-grid__item[^"]*"[^>]*>.*?'
    r'c3-product__producer"[^>]*>([^<]*)</span>\s*'
    r'<span class="c3-product__name"[^>]*>([^<]+)</span>.*?'
    r'c3-product__price-value"[^>]*>([\d,]+)</span>',
    re.S,
)
PAGE_SIZE = 48
MAX_PAGES = 40  # safety cap (40*48 ~= 1920, above the largest observed leaf)


def _extract_category_tree(text: str) -> dict:
    m = _STATE_RE.search(text)
    if not m:
        return {}
    start = m.end() - 1
    dec = json.JSONDecoder()
    js_string, _ = dec.raw_decode(text[start:])
    obj = json.loads(js_string)
    return obj.get("shop", {}).get("_categoryById", {})


class MpreisAtSpider(scrapy.Spider):
    name = "mpreis_at"
    allowed_domains = ["mpreis.at"]
    currency = "EUR"
    language = "de"

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
        yield scrapy.Request(_ROOT_URL, callback=self.parse_tree)

    def parse_tree(self, response):
        cats = _extract_category_tree(response.text)
        leaves = [
            c
            for c in cats.values()
            if not c.get("subcategories") and c.get("productCount", 0) > 0
        ]
        logger.info(f"mpreis_at: leaf categories={len(leaves)}")
        for c in leaves:
            target_page = max(1, math.ceil(c["productCount"] / PAGE_SIZE))
            yield scrapy.Request(
                f"{_BASE}{c['to']}?currentPage={target_page}",
                callback=self.parse_leaf,
                meta={
                    "category": " > ".join(c.get("pathSegments", [c["name"]])),
                    "product_count": c["productCount"],
                    "page": target_page,
                    "to": c["to"],
                },
            )

    def parse_leaf(self, response):
        category = response.meta["category"]
        expected = response.meta["product_count"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"mpreis_at: {category} products={len(cards)} expected={expected}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, producer, name, price in cards:
            full_name = f"{producer} {name}".strip() if producer else name
            yield {
                "product_id": url_path.rsplit("-", 1)[-1],
                "product_name": html.unescape(full_name).strip()[:500],
                "category": category,
                "price": price.replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        page = response.meta["page"]
        if len(cards) < expected and page < MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}{response.meta['to']}?currentPage={next_page}",
                callback=self.parse_leaf,
                meta={**response.meta, "page": next_page},
            )
