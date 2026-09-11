"""Palace Superstores (Ghana) -- https://palacesuperstores.com/.

Bespoke Laravel-style paginated JSON API at /api/products?page=N (12 items
per page, ~1,457 pages at probe time). Not WooCommerce/Shopify -- the
storefront is a custom build, so this does not subclass either shared base.

Verified live 2026-09-11 (STALE-OK retest, onboard_1.csv): plain,
non-impersonating HTTP (no curl_cffi, no Playwright) returns 200 on every
page. Enumerability confirmed: page 1/2/3 product ids fully disjoint.
Currency GHS confirmed from the PDP's own GA4 view_item tracking payload
({"currency":"GHS", ...}) -- not inferred from the Cedi symbol or the TLD.
Locality confirmed: homepage copy "For you, for your, for Ghana."
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PER_PAGE_URL = "https://palacesuperstores.com/api/products?page={page}"
MAX_PAGES = 200  # safety cap; catalog has ~1,457 pages total


class PalacesuperstoresGhSpider(scrapy.Spider):
    name = "palacesuperstores_gh"
    allowed_domains = ["palacesuperstores.com"]
    currency = "GHS"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            PER_PAGE_URL.format(page=1),
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        items = payload.get("data") if isinstance(payload, dict) else None
        if not items:
            return
        page = response.meta["page"]
        logger.info(f"{self.name} page={page} count={len(items)}")
        for p in items:
            item = self._item(p)
            if item:
                yield item
        last_page = (payload.get("meta") or {}).get("last_page")
        if page < MAX_PAGES and (last_page is None or page < last_page):
            nxt = page + 1
            yield scrapy.Request(
                PER_PAGE_URL.format(page=nxt),
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, p: dict):
        raw_price = p.get("price")
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        cats = p.get("categories") or []
        category = cats[0].get("name", "").strip() if cats and isinstance(cats[0], dict) else None
        slug = p.get("slug")
        if not slug:
            return None
        return {
            "product_id": str(p.get("sku") or p.get("id")),
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": category or None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://palacesuperstores.com/products/{slug}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
