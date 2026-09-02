"""
Spider for Namshi Oman (fashion marketplace) - namshi.com (oman-en storefront)

Namshi runs on the same platform family as noon.com (product images serve off
f.nooncdn.com, SKUs follow noon's "Z<hex>Z" pzsku pattern) but, unlike
noon.com's own `/_svc/catalog/api/v3/search` endpoint -- which defaults to
the UAE catalog regardless of an `/oman-en/` URL prefix, with no country
cookie/param found during onboarding that reliably re-scopes it to Oman --
Namshi's own category *listing pages* embed genuinely OMR-priced,
Oman-specific schema.org Product/Offer JSON-LD directly in the server-
rendered HTML. That JSON-LD only covers products carrying a rating
(nested under `aggregateRating.itemReviewed`), so a page's ~7-15 JSON-LD
Product blocks are a subset of that page's full product grid, not the
whole thing -- still real, distinct, OMR-priced rows, just partial
coverage per page.

Seeded off a fixed list of top-level category slugs (women-clothing,
men-clothing, kids-fashion, beauty, shoes, bags, home) and paginated via
`?page=N`; each category's `numberOfItems` in the JSON-LD ItemList runs into
the tens of thousands (verified live 2026-08-31: women-clothing=52,574,
men-clothing=26,086), so MAX_PAGES is a safety cap, not an expectation of
full coverage in one run. Verified distinct SKUs across pages 1/2/3 of
women-clothing (15/9/11 distinct, no repeats across pages) -- pagination
genuinely advances, not the flat-cap trap.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.namshi.com/oman-en"
_CATEGORY_SLUGS = [
    "women-clothing",
    "men-clothing",
    "kids-fashion",
    "beauty",
    "shoes",
    "bags",
    "home",
]
_MAX_PAGES = (
    1000  # safety cap per category; dedup on seen_skus ends a category at fresh=0
)
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


def _iter_products(node):
    """Recursively walk a parsed JSON-LD blob for schema.org Product nodes
    that carry an `offers` block (skips WebSite/BreadcrumbList/ItemList
    wrapper nodes)."""
    if isinstance(node, dict):
        if node.get("@type") == "Product" and node.get("offers"):
            yield node
        for value in node.values():
            yield from _iter_products(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_products(item)


class NamshiOmSpider(scrapy.Spider):
    name = "namshi_om"
    allowed_domains = ["namshi.com"]
    currency = "OMR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        self.seen_skus = set()
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                f"{_BASE}/{slug}/?page=1",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        fresh = 0
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if data is None:
                continue
            for product in _iter_products(data):
                item = self._item(product, slug)
                if item:
                    fresh += 1
                    yield item
        logger.info("namshi_om: slug=%s page=%d fresh=%d", slug, page, fresh)
        if fresh and page < _MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/{slug}/?page={page + 1}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": page + 1},
            )

    def _item(self, product: dict, slug: str):
        sku = product.get("sku")
        if not sku or sku in self.seen_skus:
            return None
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", "0", "0.00"):
            return None
        self.seen_skus.add(sku)
        brand = product.get("brand")
        full_name = f"{brand} {name}" if brand and brand not in name else name
        return {
            "product_id": sku,
            "product_name": str(full_name)[:500],
            "category": offers.get("category") or slug,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offers.get("availability") or ""),
            "url": offers.get("url") or product.get("url") or "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
