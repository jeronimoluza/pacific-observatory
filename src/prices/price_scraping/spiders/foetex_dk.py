"""
Spider for føtex (Denmark) — https://www.foetex.dk.

Nuxt storefront (Salling Group, same family as bilkatogo_dk). No product
data on the plain-HTTP HTML (category pages are client-rendered), but the
storefront calls Algolia directly from the browser. Playwright
network-capture (2026-09-06) on a category page found the app id
(DRP4O45G5T) and a search-only API key compiled into the page's runtime
config -- both are meant to be public per Algolia's own model. The key is
scoped to a single index, prod_FOETEX_PRODUCTS (Salling Group's other
brand indices, e.g. prod_BILKATOGO_PRODUCTS, 403 with this key, per
bilkatogo_dk's docstring -- the reverse is assumed true and untested).

Unlike bilkatogo_dk, `sales_price` here is already a decimal DKK amount
(NOT minor units / øre) -- confirmed live 2026-09-06: 'Æblechips til
gnavere' sales_price=22.45, 'Æblebrændevin' sales_price=299.0, matching
the site's own da-DK display fields (display_sales_price "22,45" /
"299,-"). Filtering `is_exposed:true` excludes unpublished/inactive SKUs
(an unfiltered query returns records with is_exposed=false mixed in).
61,912 exposed products confirmed live 2026-09-06, hitsPerPage=1000 -> 60
pages for the full catalogue (mixed food + general-merchandise
hypermarket range, per AI_NOTES).
"""

import html
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://drp4o45g5t-dsn.algolia.net/1/indexes/*/queries"
_APP_ID = "DRP4O45G5T"
_API_KEY = "f3a34fc94874579eaf3cd39fef660948"
_INDEX = "prod_FOETEX_PRODUCTS"
_HITS_PER_PAGE = 1000
_MAX_PAGES = 70  # safety cap; confirmed nbPages=60 live 2026-09-06


class FoetexDkSpider(scrapy.Spider):
    name = "foetex_dk"
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
        params = f"query=&filters=is_exposed%3Atrue&hitsPerPage={_HITS_PER_PAGE}&page={page}"
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
            logger.warning("foetex_dk: non-JSON response at %s", response.url)
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
        name = html.unescape((h.get("name") or "").strip())
        if not name:
            return None
        price = h.get("sales_price")
        if price is None:
            return None
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        cats = h.get("category") or []
        category = " > ".join(cats) if isinstance(cats, list) and cats else None
        oid = str(h.get("objectID") or "")
        canonical = h.get("canonical_url") or ""
        url = f"https://www.foetex.dk{canonical}" if canonical else f"https://www.foetex.dk/produkter/{oid}/"
        return {
            "product_id": oid,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
