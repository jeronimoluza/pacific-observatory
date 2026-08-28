"""
Spider for Bilka ToGo (Denmark) — https://www.bilkatogo.dk.

Nuxt storefront (Salling Group). No product data on the plain-HTTP homepage,
but the storefront itself calls Algolia directly from the browser: the app
id (F9VBJLR1BK) and a search-only API key are compiled straight into the
Nuxt JS bundle (_nuxt/f6afb7b.js, NUXT_ENV_ALGOLIA_APP_ID + the literal key
next to it) — both are meant to be public per Algolia's own model. The key
is scoped to a single index, prod_BILKATOGO_PRODUCTS (other Salling
Group indices, e.g. prod_FOETEX_PRODUCTS, 403 with this key).
Re-verified live 2026-08-06: POST
https://F9VBJLR1BK-dsn.algolia.net/1/indexes/*/queries -> HTTP 200 JSON,
nbHits 37,259, hitsPerPage=1000 accepted (30 pages for the full catalogue).
Sample: 'Agurk' (cucumber) 1100 -> 11.00 DKK; 'Bananer 4 pak øko' 1000 ->
10.00 DKK. `price`/`sales_price` are minor units (øre) — divide by 100.
"""

import html
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://F9VBJLR1BK-dsn.algolia.net/1/indexes/*/queries"
_APP_ID = "F9VBJLR1BK"
_API_KEY = "1deaf41c87e729779f7695c00f190cc9"
_INDEX = "prod_BILKATOGO_PRODUCTS"
_HITS_PER_PAGE = 1000
_MAX_PAGES = 40
_ATTRS = [
    "name",
    "productName",
    "price",
    "sales_price",
    "uom",
    "netcontent",
    "brand",
    "objectID",
]


class BilkatogoDkSpider(scrapy.Spider):
    name = "bilkatogo_dk"
    allowed_domains = ["algolia.net"]
    currency = "DKK"
    language = "da"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, page: int):
        params = (
            f"hitsPerPage={_HITS_PER_PAGE}&page={page}"
            f"&attributesToRetrieve={json.dumps(_ATTRS)}"
        )
        body = {"requests": [{"indexName": _INDEX, "params": params}]}
        return scrapy.Request(
            _URL,
            method="POST",
            headers={
                "X-Algolia-API-Key": _API_KEY,
                "X-Algolia-Application-Id": _APP_ID,
                "Content-Type": "application/json",
            },
            body=json.dumps(body),
            callback=self.parse_page,
            meta={"page": page},
        )

    async def start(self):
        yield self._request(0)

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning("bilkatogo_dk: non-JSON response at %s", response.url)
            return
        results = data.get("results") or []
        if not results:
            return
        result = results[0]
        hits = result.get("hits") or []
        page = response.meta["page"]
        for h in hits:
            item = self._item(h)
            if item:
                yield item
        n_pages = result.get("nbPages", 0)
        if hits and page + 1 < min(n_pages, _MAX_PAGES):
            yield self._request(page + 1)

    def _item(self, h: dict):
        name = html.unescape((h.get("name") or h.get("productName") or "").strip())
        if not name:
            return None
        netcontent = (h.get("netcontent") or "").strip()
        if netcontent and netcontent.lower() not in name.lower():
            name = f"{name} {netcontent}"
        raw_price = h.get("sales_price") or h.get("price")
        if raw_price is None:
            return None
        try:
            price = float(raw_price) / 100.0
        except (TypeError, ValueError):
            return None
        oid = str(h.get("objectID") or "")
        return {
            "product_id": oid,
            "product_name": name[:500],
            "category": h.get("brand") or None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://www.bilkatogo.dk/produkt/{oid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
