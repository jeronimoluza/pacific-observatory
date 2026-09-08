"""
Spider for Rappi Peru (market vertical) -- https://www.rappi.com.pe/.

Delivery aggregator enumerating Peruvian partner supermarkets/bodegas
(GOTCHA: platform markup likely -- prices reflect Rappi's marked-up
in-app price, not necessarily the store's own shelf price). `channel:
marketplace` reflects this.

Next.js SSR embeds everything needed with no separate API calls required
at collection time (confirmed live 2026-09-06):

1. `/lima/tiendas/tipo/market` -> __NEXT_DATA__.props.pageProps.fallback
   (single react-query cache entry) -> `storeGroups[*].stores[]`, each
   carrying `storeId` + `friendlyURL` (e.g. "64816-greta-market-nc").
2. `/tiendas/<friendlyURL>` (store home) -> fallback ->
   `aisles_tree_response.data.components[]`, each an aisle with
   `resource.friendly_url` (e.g. "vitaminas-y-suplementos") and
   `product_count`.
3. `/tiendas/<friendlyURL>/<aisle_friendly_url>` -> fallback ->
   `sub_aisles_response.data.components[]` where `render == "aisle"` ->
   `resource.products[]` -- full product rows with `price` (the
   charged/discounted price), `real_price` (pre-discount), `category_name`,
   `in_stock`.

Verified live: store 64816 (Greta Market Saludable) aisle
"vitaminas-y-suplementos" -> sub-aisle "Salud Digestiva y Probioticos" ->
product "Vivir Psyllium Husk Doypack 284g", price PEN 42.50 (real_price 50).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.rappi.com.pe"
_STORE_LIST_URL = f"{_BASE}/lima/tiendas/tipo/market"
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_STORE_STRIDE = 3  # sample every Nth store from the market listing
MAX_AISLES_PER_STORE = 4  # bound requests per store


def _first_fallback_value(pp: dict):
    fb = pp.get("fallback") or {}
    for v in fb.values():
        return v
    return None


class RappiPeSpider(scrapy.Spider):
    name = "rappi_pe"
    allowed_domains = ["rappi.com.pe"]
    currency = "PEN"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_STORE_LIST_URL, callback=self.parse_store_list)

    def _extract_next_data(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

    def parse_store_list(self, response):
        data = self._extract_next_data(response)
        if not data:
            logger.warning("rappi_pe: no __NEXT_DATA__ at %s", response.url)
            return
        pp = data.get("props", {}).get("pageProps", {})
        val = _first_fallback_value(pp)
        if not val:
            logger.warning("rappi_pe: no fallback data at %s", response.url)
            return
        stores = []
        for group in val.get("storeGroups") or []:
            stores.extend(group.get("stores") or [])
        seen = set()
        uniq = []
        for s in stores:
            fu = s.get("friendlyURL")
            if fu and fu not in seen:
                seen.add(fu)
                uniq.append(s)
        sampled = uniq[::_STORE_STRIDE]
        logger.info("rappi_pe: sampled %d/%d stores", len(sampled), len(uniq))
        for s in sampled:
            url = f"{_BASE}/tiendas/{s['friendlyURL']}"
            yield scrapy.Request(
                url,
                callback=self.parse_store_home,
                meta={"store_name": s.get("name"), "friendly_url": s["friendlyURL"]},
            )

    def parse_store_home(self, response):
        friendly_url = response.meta["friendly_url"]
        data = self._extract_next_data(response)
        if not data:
            return
        pp = data.get("props", {}).get("pageProps", {})
        val = _first_fallback_value(pp)
        if not val:
            return
        tree = (val.get("aisles_tree_response") or {}).get("data", {})
        aisles = tree.get("components") or []
        count = 0
        for aisle in aisles:
            resource = aisle.get("resource") or {}
            fu = resource.get("friendly_url")
            if not fu:
                continue
            count += 1
            if count > MAX_AISLES_PER_STORE:
                break
            url = f"{_BASE}/tiendas/{friendly_url}/{fu}"
            yield scrapy.Request(
                url,
                callback=self.parse_aisle,
                meta={
                    "store_name": response.meta["store_name"],
                    "friendly_url": friendly_url,
                    "aisle_name": resource.get("name"),
                },
            )

    def parse_aisle(self, response):
        data = self._extract_next_data(response)
        if not data:
            return
        pp = data.get("props", {}).get("pageProps", {})
        val = _first_fallback_value(pp)
        if not val:
            return
        sub = (val.get("sub_aisles_response") or {}).get("data", {})
        components = sub.get("components") or []
        for comp in components:
            if comp.get("render") != "aisle":
                continue
            resource = comp.get("resource") or {}
            for product in resource.get("products") or []:
                item = self._item(product, response.meta)
                if item:
                    yield item

    def _item(self, product: dict, meta: dict):
        name = (product.get("name") or "").strip()
        product_id = str(product.get("product_id") or product.get("id") or "")
        price = product.get("price")
        if not name or not product_id or price in (None, "", 0):
            return None
        category = product.get("category_name") or meta.get("aisle_name")
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(product.get("in_stock", True)),
            # Synthetic per-product URL: aisle pages have no PDP, and the
            # dedup pipeline keys on url, so a bare store URL would collapse
            # every product in a store into one record (confirmed live --
            # 268/274 items dropped as duplicates before this fix).
            "url": f"{_BASE}/tiendas/{meta['friendly_url']}#{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
