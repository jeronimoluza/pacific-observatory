"""
Spider for tradeling.com -- UAE B2B wholesale marketplace (Next.js storefront,
separate microservices backend at api.tradeling.com). Registered as covering
~22 MENA countries, but the storefront and this spider default to the `ae-en`
(United Arab Emirates, AED) locale only -- no other country is scraped here.

**This is a B2B wholesale catalog, not retail.** Every row carries a
`minOrderQty`, per-supplier `unitsPerCarton` packaging, and enterprise-vs-
individual price tiers -- prices reflect wholesale/bulk unit pricing, not a
walk-in retail shelf price, and are not directly comparable to retailer_sku
rows from consumer storefronts.

Catalog walk: the storefront's own product-search endpoint
(`POST /api/catalog-search/v4/products/search`, body `{"sort":"",
"filter":{"attributes":{},"currentPage":N,"source":"catalog",
"storeName":"all","categorySlug":"<slug>"}}`) returns priced rows for a
guest session -- the `x-jwt-token` header is sent as an empty string, no
login or quote request needed to see indicative unit pricing
(`searchPricesWithVat.minPriceAED`). Confirmed live 2026-08-17: plain
`requests` (no TLS impersonation) gets a clean 200, so no impersonation is
used here.

The 14 top-level category slugs below come from
`https://c8n.tradeling.com/sitemaps/sitemap-parent-category-0.xml` and each
resolves directly against the search endpoint (an empty `categorySlug`
returns zero records -- a real L1/L2/L3 slug is required). Enumerability
proven live: `categorySlug=canned-food` page 1 vs page 2 returned fully
disjoint product-id sets (0 overlap), and top-level slugs like
`food-beverage` report `totalPages: 50` at `pageSize: 40`.

Product-detail URLs are reconstructed from the PDP sitemap's observed slug
pattern (`/ae-en/product-details/<slugified-name>-<productId>-
<supplierCompanyId>`, verified against a real sitemap entry), since the
search response carries no direct PDP link -- best-effort, not guaranteed
to resolve for every row, but `product_id` (the SKU) is the stable key.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.tradeling.com"
_API = "https://api.tradeling.com/api/catalog-search/v4/products/search"
_MAX_PAGES = 50  # observed cap on this endpoint's own totalPages

_L1_CATEGORY_SLUGS = [
    "automotive",
    "baby-center",
    "beauty-personal-care",
    "construction-hardware",
    "electronics-2",
    "fashion-accessories",
    "food-beverage",
    "health-wellbeing",
    "home-garden-furniture",
    "machinery-equipment",
    "office-stationery",
    "pet-animal-center",
    "sports-fitness-2",
    "toys-1",
]

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9\s-]")
_SLUG_WS_RE = re.compile(r"\s+")


def _slugify(name: str) -> str:
    s = _SLUG_STRIP_RE.sub("", name.lower())
    return _SLUG_WS_RE.sub("-", s).strip("-")


def _headers():
    return {
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*",
        "x-jwt-token": "",
        "origin": _BASE,
        "referer": f"{_BASE}/",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _body(slug: str, page: int) -> str:
    return json.dumps(
        {
            "sort": "",
            "filter": {
                "attributes": {},
                "currentPage": page,
                "source": "catalog",
                "storeName": "all",
                "categorySlug": slug,
            },
        }
    )


class TradelingAeSpider(scrapy.Spider):
    name = "tradeling_ae"
    allowed_domains = ["tradeling.com"]
    currency = "AED"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _L1_CATEGORY_SLUGS:
            yield scrapy.Request(
                _API,
                method="POST",
                headers=_headers(),
                body=_body(slug, 1),
                callback=self.parse_search,
                meta={"slug": slug, "page": 1},
            )

    def parse_search(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            return
        products = ((data.get("data") or {}).get("products")) or []
        total_pages = data.get("totalPages") or 0
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for row in products:
            product_id = row.get("sku") or row.get("id")
            name = row.get("name")
            prices = row.get("searchPricesWithVat") or row.get("searchPrices") or {}
            price = prices.get("minPriceAED") or prices.get("retailPriceAED")
            if not (product_id and name and price is not None):
                continue
            names = row.get("categoryNames") or {}
            category = " > ".join(
                v
                for v in (
                    names.get("l1"),
                    names.get("l2"),
                    names.get("l3"),
                    names.get("l4"),
                )
                if v
            ) or " > ".join(row.get("categorySlugs") or [])
            product_slug = _slugify(str(name))
            supplier_id = row.get("supplierCompanyId") or ""
            url = f"{_BASE}/ae-en/product-details/{product_slug}-{row.get('id')}-{supplier_id}"
            n += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip()[:500],
                "category": category or None,
                "price": str(price),
                "currency": self.currency,
                "available": (row.get("stockQty") or 0) > 0,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: slug={slug} page={page} rows={n}")
        if page < total_pages and page < _MAX_PAGES:
            yield scrapy.Request(
                _API,
                method="POST",
                headers=_headers(),
                body=_body(slug, page + 1),
                callback=self.parse_search,
                meta={"slug": slug, "page": page + 1},
            )
