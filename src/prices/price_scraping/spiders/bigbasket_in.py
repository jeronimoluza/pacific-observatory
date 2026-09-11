"""
Spider for BigBasket (India) -- https://www.bigbasket.com/

Next.js SSR storefront: plain curl/Scrapy requests to a `/pc/<category-slug>/`
listing page succeed with no WAF and return `__NEXT_DATA__` embedding
`props.pageProps.SSRData.tabs[*].product_info.products` -- ~48 products per
page, paginated with `&page=N` (confirmed distinct product ids page 1 vs
page 2, no overlap, verified 2026-09-11).

Category slugs are hardcoded to the food/beverage/alcohol-relevant top-level
categories (the classifier routes individual SKUs to a leaf, so a broad food
category sweep is the point, not narrow filtering). Each category is walked
until a page contributes zero new product ids (handles the "flat cap /
re-served last page" trap) or MAX_PAGES is hit.

Price: `pricing.discount.prim_price.sp` (selling price) with fallback to
`pricing.discount.mrp` (list price) when no discount is active. Currency is
INR at the spider-class level (India-only storefront), not inferred from the
page.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)

_CATEGORY_SLUGS = [
    "fruits-vegetables",
    "foodgrains-oil-masala",
    "bakery-cakes-dairy",
    "beverages",
    "eggs-meat-fish",
    "gourmet-world-food",
    "snacks-branded-foods",
]

_MAX_PAGES = 15


class BigbasketInSpider(scrapy.Spider):
    name = "bigbasket_in"
    allowed_domains = ["bigbasket.com"]
    currency = "INR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 2,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                f"https://www.bigbasket.com/pc/{slug}/?page=1",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1, "seen_ids": set()},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        seen_ids = response.meta["seen_ids"]

        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.info(f"bigbasket_in: no __NEXT_DATA__ on {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return

        tabs = (
            data.get("props", {})
            .get("pageProps", {})
            .get("SSRData", {})
            .get("tabs", [])
        )
        products = []
        for tab in tabs:
            products.extend(tab.get("product_info", {}).get("products", []) or [])

        new_ids = set()
        for p in products:
            pid = p.get("id")
            if not pid or pid in seen_ids:
                continue
            new_ids.add(pid)
            item = self._to_item(p, response.url)
            if item:
                yield item

        if not new_ids:
            logger.info(
                f"bigbasket_in: {slug} page {page} contributed 0 new ids, stopping"
            )
            return

        if page >= _MAX_PAGES:
            return

        seen_ids = seen_ids | new_ids
        yield scrapy.Request(
            f"https://www.bigbasket.com/pc/{slug}/?page={page + 1}",
            callback=self.parse_category,
            meta={"slug": slug, "page": page + 1, "seen_ids": seen_ids},
        )

    def _to_item(self, p: dict, url: str) -> dict | None:
        pid = p.get("id")
        name = p.get("desc")
        if not pid or not name:
            return None
        pack = p.get("w") or p.get("pack_desc")
        full_name = f"{name} {pack}".strip() if pack else name

        pricing = p.get("pricing", {}) or {}
        discount = pricing.get("discount", {}) or {}
        prim = discount.get("prim_price", {}) or {}
        price = prim.get("sp") or discount.get("mrp")
        if price is None:
            return None

        rel_url = p.get("absolute_url") or ""
        product_url = (
            f"https://www.bigbasket.com{rel_url}" if rel_url.startswith("/") else url
        )

        avail = p.get("availability", {}) or {}
        available = not avail.get("not_for_sale", False)

        return {
            "product_id": str(pid),
            "product_name": str(full_name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": available,
            "url": product_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
