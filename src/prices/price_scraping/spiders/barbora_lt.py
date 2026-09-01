"""
Barbora (Lithuania) — https://barbora.lt/.

Maxima Group's e-grocery storefront — a DIFFERENT chain from Rimi
(rimi_lt / rimi_wolt_lt), which is the whole point of this source: it is
Lithuania's largest supermarket group's online catalog, independent of the
Rimi corporate platform.

Custom C#/"cshtml" storefront (not Shopify/Woo/Magento/VTEX). The homepage
embeds `window.b_urls.eShopApiBaseUrl = "/api/eshop/v1/"`, and that API's
search endpoint is fully open and SSR-served with clean offset pagination:

    GET /api/eshop/v1/search?query=<term>&limit=<n>&offset=<n>
    -> {"count": <total matches>, "products": [{...}]}

Confirmed live 2026-08-31: `query=` is the working param name (guessed
`q`/`phrase`/`term`/`searchString` all return `count: 0`); `limit`/`offset`
are honoured (verified offset=0/50/100 on "pienas" returns 50 distinct
products each hop, zero overlap). No category-browse endpoint was found
(guessed `/category/<id>`, `/category-products`, etc. all 404) — coverage
here is a keyword-search sweep across common grocery nouns, same approach
already used for `_rimi_baltic_base` on this same market, since no browse
API exists on either platform.

Each product row carries a `Url` slug; the product detail page lives at
`https://barbora.lt/produktai/<slug>` — confirmed 200 with the product name
present in the raw HTML for a sampled row.

`price` is the current (possibly promo) selling price in EUR; Lithuania's
currency, and the only currency the site ever emits (no explicit currency
field in the payload, but the storefront is LT-only and prices are exactly
in the range expected for EUR grocery SKUs, e.g. 1.79 EUR sour cream).
"""

import html
import logging
import urllib.parse
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://barbora.lt"
SEARCH_API = f"{BASE_URL}/api/eshop/v1/search"
_PAGE_LIMIT = 50
_MAX_OFFSET_PER_TERM = (
    300  # safety cap: 6 pages/term, well above any single-noun count seen
)


class BarboraLtSpider(scrapy.Spider):
    name = "barbora_lt"
    allowed_domains = ["barbora.lt"]
    currency = "EUR"
    language = "lt"

    SEARCH_TERMS = [
        "pienas",
        "duona",
        "sūris",
        "kiaušiniai",
        "mėsa",
        "vištiena",
        "žuvis",
        "jogurtas",
        "sviestas",
        "cukrus",
        "miltai",
        "ryžiai",
        "makaronai",
        "kava",
        "arbata",
        "sultys",
        "vanduo",
        "alus",
        "vynas",
        "šokoladas",
        "sausainiai",
        "konservai",
        "daržovės",
        "vaisiai",
        "dešra",
    ]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, term: str, offset: int):
        q = urllib.parse.quote(term)
        return scrapy.Request(
            f"{SEARCH_API}?query={q}&limit={_PAGE_LIMIT}&offset={offset}",
            callback=self.parse_page,
            headers={
                "Accept": "application/json",
                "Referer": f"{BASE_URL}/paieska?q={q}",
            },
            meta={"term": term, "offset": offset},
        )

    async def start(self):
        for term in self.SEARCH_TERMS:
            yield self._request(term, 0)

    def parse_page(self, response):
        term = response.meta["term"]
        offset = response.meta["offset"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        products = data.get("products") or []
        for p in products:
            item = self._item(p)
            if item:
                yield item

        count = data.get("count") or 0
        next_offset = offset + _PAGE_LIMIT
        logger.info(
            f"{self.name}: term={term} offset={offset} got={len(products)} total={count}"
        )
        if products and next_offset < count and next_offset < _MAX_OFFSET_PER_TERM:
            yield self._request(term, next_offset)

    def _item(self, p: dict):
        name = (p.get("title") or "").strip()
        price = p.get("price")
        pid = str(p.get("id") or "")
        slug = p.get("Url") or ""
        if not name or price is None or not pid:
            return None
        return {
            "product_id": pid,
            "product_name": html.unescape(name)[:500],
            "category": p.get("category_name_full_path") or None,
            "price": str(price),
            "currency": self.currency,
            "available": p.get("status") == "active",
            "url": f"{BASE_URL}/produktai/{slug}" if slug else f"{SEARCH_API}#{pid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
