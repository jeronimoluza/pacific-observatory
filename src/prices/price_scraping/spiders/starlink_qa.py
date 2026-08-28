"""
Spider for starlink.qa — Qatar electronics/mobile retailer (Starlink Qatar).

The shard probe flagged this as "Shopify" (gid://shopify/ object IDs) but its
storefront is a custom Vue/Quasar app on top of the Shopify Storefront
GraphQL API — NOT the classic Liquid theme. Verified live 2026-08-17 that
both routes ShopifyBaseSpider depends on are dead ends:
  - https://starlink.qa/products.json -> 200 but returns the app-shell HTML
    (intercepted by the custom frontend), not JSON.
  - https://starlink1.myshopify.com/products.json (the underlying
    *.myshopify.com store) -> 401 (storefront-locked).
So this is a standalone spider, not a ShopifyBaseSpider subclass.

Real data source: every /en/collections/<handle> page (and the product page)
server-renders `window.__INITIAL_STATE__ = {...}` containing the exact
Shopify Storefront GraphQL response for that collection — full product list
with variants/sku/price, no auth needed. The "all" collection SSRs only its
first 20 products with no working pagination (?page=N is ignored server-side
-- confirmed identical id sets on page=1 vs page=2, the homepage-carousel
trap this wave is watching for). The catalog IS walkable, just not through
"all": the site's own allCategoriesMenu lists ~123 real leaf category
handles (iphones, laptops, gaming-mouse, wiwu-cables, ...), and each one
SSRs its own distinct product slice (confirmed live: /collections/all vs
/collections/mobile-phones share only 7/20 products -- genuine per-category
content, not one carousel reused everywhere). This spider discovers that
handle list from the "all" page's menu state, then walks every handle.

currency hardcoded to QAR (the site's own display price, e.g. "QAR 829.00"
on product cards) -- the GraphQL price.currencyCode field is null in this
tenant's response.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://starlink.qa"
_STATE_MARKER = "window.__INITIAL_STATE__="


def _extract_state(text: str):
    idx = text.find(_STATE_MARKER)
    if idx == -1:
        return None
    start = idx + len(_STATE_MARKER)
    try:
        data, _ = json.JSONDecoder().raw_decode(text, start)
    except (ValueError, TypeError):
        return None
    return data


def _collect_handles(items: dict, out: set):
    for key, value in items.items():
        if not key.startswith("gid://"):
            out.add(key)
        if isinstance(value, dict) and value.get("items"):
            _collect_handles(value["items"], out)


class StarlinkQaSpider(scrapy.Spider):
    name = "starlink_qa"
    allowed_domains = ["starlink.qa"]
    currency = "QAR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(f"{_BASE}/en/collections/all", callback=self.parse_menu)

    def parse_menu(self, response):
        data = _extract_state(response.text)
        if not data:
            logger.warning("starlink_qa: no __INITIAL_STATE__ on menu page")
            return
        menu = (
            (data.get("menu") or {})
            .get("state", {})
            .get("allCategoriesMenu", {})
            .get("items", {})
        )
        handles = set()
        _collect_handles(menu, handles)
        handles.add("all")
        logger.info(f"starlink_qa: {len(handles)} category handles discovered")
        for handle in sorted(handles):
            yield scrapy.Request(
                f"{_BASE}/en/collections/{handle}",
                callback=self.parse_collection,
                meta={"handle": handle},
            )

    def parse_collection(self, response):
        handle = response.meta["handle"]
        data = _extract_state(response.text)
        if not data:
            return
        collection = (
            (data.get("product") or {})
            .get("state", {})
            .get("collectionByHandle", {})
            .get("collection")
        )
        if not collection:
            return
        products = collection.get("products") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for p in products:
            p_handle = p.get("handle")
            title = (p.get("title") or "").strip()
            if not (p_handle and title):
                continue
            variants = ((p.get("variants") or {}).get("nodes")) or []
            for v in variants:
                price_block = v.get("price") or {}
                amount = price_block.get("amount")
                if amount is None:
                    continue
                sku = v.get("sku") or p.get("id") or p_handle
                v_title = (v.get("title") or "").strip()
                name = (
                    title
                    if v_title in ("Default Title", "")
                    else f"{title} ({v_title})"
                )
                category = ((v.get("product") or {}).get("productType")) or None
                n += 1
                yield {
                    "product_id": str(sku),
                    "product_name": name[:500],
                    "category": category,
                    "price": str(amount),
                    "currency": self.currency,
                    "available": bool(p.get("availableForSale", True)),
                    "url": f"{_BASE}/en/products/{p_handle}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
        logger.info(f"starlink_qa: handle={handle} rows={n}")
