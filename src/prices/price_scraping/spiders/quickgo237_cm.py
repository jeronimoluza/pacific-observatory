"""Spider for QuickGo237 (Cameroon) -- https://quickgo237.com/.

Next.js multi-vendor local marketplace (restaurants + grocery/pharmacy/
electronics vendors) backed by a plain JSON API, no auth required. Verified
live 2026-09-11: GET https://www.quickgo237.com/api/products?limit=50&offset=0
-> 200, flat catalog of 11 products across ~4 vendors (Restaurant Le
Gourmet, Super U Express, Oneclick, ...). Enumerability verified:
limit=5&offset=0 vs limit=5&offset=5 return disjoint id sets; the API
reports {"count": 11} and 500s past that offset (their own off-by-one bug,
not a block). Prices are plain integers in XAF (displayed "155 000 FCFA" /
"4 500 FCFA" on the rendered page; API has no explicit currency field, but
this is a Cameroon-only storefront so XAF is unambiguous). PDP permalink
pattern confirmed live: /marketplace/product/<slug> (200; note singular
"product", not the "/products.json"-style plural used elsewhere on the
site). Catalog is small (11 SKUs) -- an early-stage marketplace, not yet a
mature catalog -- but every hard gate (enumerable, priced, local currency,
local vendors) passes.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://www.quickgo237.com/api/products"
_PAGE_SIZE = 50


class Quickgo237CmSpider(scrapy.Spider):
    name = "quickgo237_cm"
    allowed_domains = ["quickgo237.com", "www.quickgo237.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        yield scrapy.Request(
            f"{_API}?limit={_PAGE_SIZE}&offset=0",
            callback=self.parse,
            headers={
                "Referer": "https://quickgo237.com/marketplace/products",
                "Accept": "application/json",
            },
            meta={"offset": 0},
        )

    def parse(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        products = data.get("data") if isinstance(data, dict) else data
        if not products:
            return
        total = data.get("count") if isinstance(data, dict) else None
        offset = response.meta["offset"]
        logger.info(f"{self.name}: offset={offset} got={len(products)} total={total}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("price")
            if price is None:
                continue
            slug = p.get("slug") or p.get("id")
            category = None
            cat = p.get("category")
            if isinstance(cat, dict):
                category = cat.get("name")
            elif isinstance(cat, str):
                category = cat
            yield {
                "product_id": str(p.get("id") or slug),
                "product_name": str(p.get("name") or "").strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("is_available", True)),
                "url": f"https://quickgo237.com/marketplace/product/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        next_offset = offset + _PAGE_SIZE
        if total is not None and next_offset < total:
            yield scrapy.Request(
                f"{_API}?limit={_PAGE_SIZE}&offset={next_offset}",
                callback=self.parse,
                headers={
                    "Referer": "https://quickgo237.com/marketplace/products",
                    "Accept": "application/json",
                },
                meta={"offset": next_offset},
            )
