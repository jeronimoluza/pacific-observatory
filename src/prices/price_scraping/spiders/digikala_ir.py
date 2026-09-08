"""
Digikala (Iran) -- https://www.digikala.com/, Iran's dominant general
marketplace.

The public site is a bare Next.js SPA shell (curl_cffi gets a
hydration-free document with no product HTML), but the app's own data API
at https://api.digikala.com has no anti-bot at all and returns clean JSON:

    GET /v1/categories/<slug>/search/ -> {"data": {"products": [...], "pager": {...}}}

Verified live 2026-09-06 across 18 category slugs (mobile-phone, laptop,
tablet, digital-camera, smart-watch, home-appliance, personal-care,
perfume, toothpaste, toaster, chocolate, canned-food, pasta, dairy,
cheese, diaper, rice, tea) -- every slug returned 20 products/page with
plausible totals (e.g. rice: 3,043 items; tea: 7,346 items). Not every
guessed slug resolves (many return a bare {"status":404}); the slug list
below is the confirmed-working subset, spanning electronics, personal
care and food so the classifier sees more than one COICOP division.

Price unit: `default_variant.price.selling_price` is recorded as IRR
(Iranian Rial) as-is, no multiplier applied. This is an ASSUMPTION, not a
verified fact -- Digikala's own API also exposes a differently-named
`selling_price_tooman` field elsewhere in its surface (per public
third-party API docs), which implies the plain `selling_price` field is
the Rial figure, but this was not cross-checked against a rendered
product page (the SPA shell carries no price text server-side). If a
future audit finds prices are 10x too high/low, check this first
(compare against known Toman-quoting sources' PRICE_MULTIPLIER=10
convention, e.g. adibmarket_ir.yaml).

Pagination: `page=N` (1-indexed); stops when a page returns fewer than
20 products, capped at 10 pages/category (200 items) to bound total
requests across 18 categories.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://api.digikala.com/v1/categories"
_PER_PAGE = 20
_MAX_PAGES = 10

_CATEGORY_SLUGS = [
    "mobile-phone",
    "laptop",
    "tablet",
    "digital-camera",
    "smart-watch",
    "home-appliance",
    "personal-care",
    "perfume",
    "toothpaste",
    "toaster",
    "chocolate",
    "canned-food",
    "pasta",
    "dairy",
    "cheese",
    "diaper",
    "rice",
    "tea",
]


class DigikalaIrSpider(scrapy.Spider):
    name = "digikala_ir"
    allowed_domains = ["digikala.com"]
    currency = "IRR"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "CONCURRENT_REQUESTS": 3,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 30,
    }

    async def start(self):
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                self._url(slug, 1),
                callback=self.parse_page,
                meta={"slug": slug, "page": 1},
            )

    @staticmethod
    def _url(slug: str, page: int) -> str:
        return f"{_BASE}/{slug}/search/?page={page}"

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"digikala_ir: non-JSON response at {response.url}")
            return
        products = (payload.get("data") or {}).get("products") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for entry in products:
            item = self._item(entry, slug, scraped_at)
            if item:
                count += 1
                yield item
        logger.info(f"digikala_ir: {slug} page={page} items={count}")

        if len(products) >= _PER_PAGE and page < _MAX_PAGES:
            yield scrapy.Request(
                self._url(slug, page + 1),
                callback=self.parse_page,
                meta={"slug": slug, "page": page + 1},
            )

    def _item(self, entry: dict, slug: str, scraped_at: str):
        title = entry.get("title_en") or entry.get("title_fa")
        if not title:
            return None
        dv = entry.get("default_variant") or {}
        price = (dv.get("price") or {}).get("selling_price")
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        pid = entry.get("id")
        uri = (entry.get("url") or {}).get("uri")
        return {
            "product_id": str(pid) if pid else None,
            "product_name": str(title).strip()[:500],
            "category": slug,
            "price": str(price),
            "currency": self.currency,
            "available": entry.get("status") == "marketable",
            "url": f"https://www.digikala.com{uri}" if uri else None,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
