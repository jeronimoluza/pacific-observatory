"""
Spider for AM PM Pharmacy (Malaysia) — store.pmg2u.com.

ampmpharmacy.com redirects to this WooCommerce storefront. The public
WooCommerce Store API at /wp-json/wc/store/v1/products?per_page=100&page=N
returns full product objects with name, sku, prices.{price,currency_code,
currency_minor_unit}, categories, permalink, is_in_stock (~1479 products).
We paginate until a short/empty page is returned.

WooCommerce returns integer prices in the smallest currency unit; the Store
API exposes currency_minor_unit so we rescale (minor_unit=2 -> 1490 = MYR 14.90).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://store.pmg2u.com/wp-json/wc/store/v1/products"
PER_PAGE = 100
MAX_PAGES = 200  # safety cap


class AmpmPharmacySpider(scrapy.Spider):
    name = "ampm_pharmacy"
    allowed_domains = ["store.pmg2u.com"]
    currency = "MYR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE}?per_page={PER_PAGE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info(f"ampm_pharmacy page={page} count={len(products)}")
        for p in products:
            yield from self._rows(p)
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}?per_page={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _rescale(self, prices: dict, raw):
        try:
            minor = int(prices.get("currency_minor_unit", 0) or 0)
            return int(raw) / (10**minor) if minor else int(raw)
        except (TypeError, ValueError):
            return raw

    def _label(self, v: dict):
        return " / ".join(
            str(a.get("value")) for a in (v.get("attributes") or []) if a.get("value")
        ).strip()

    def _row(self, p: dict, prices: dict, pid: str, name: str, value):
        cats = p.get("categories") or []
        cat = (
            " > ".join(
                c.get("name") for c in cats if isinstance(c, dict) and c.get("name")
            )
            or None
        )
        return {
            "product_id": pid,
            "product_name": name.strip()[:500],
            "category": cat,
            "price": str(value),
            "currency": prices.get("currency_code") or self.currency,
            "available": bool(p.get("is_in_stock", True)),
            "url": p.get("permalink") or "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _rows(self, p: dict):
        prices = p.get("prices") or {}
        raw = prices.get("price")
        if raw is None:
            return
        base_id = str(p.get("sku") or p.get("id"))
        name = str(p.get("name") or "")
        variations = p.get("variations") or []
        prange = prices.get("price_range") or None
        differ = (
            prange
            and prange.get("min_amount") is not None
            and prange.get("max_amount") is not None
            and str(prange.get("min_amount")) != str(prange.get("max_amount"))
        )
        if differ and len(variations) > 1:
            yield self._variation_request(p)
            return
        value = self._rescale(prices, raw)
        if variations:
            for v in variations:
                label = self._label(v)
                vname = f"{name} - {label}" if label else name
                yield self._row(p, prices, f"{base_id}_{v.get('id')}", vname, value)
        else:
            yield self._row(p, prices, base_id, name, value)

    def _variation_request(self, p: dict):
        pid = p.get("id")
        labels = {str(v.get("id")): self._label(v) for v in (p.get("variations") or [])}
        return scrapy.Request(
            f"{BASE}?type=variation&parent={pid}&per_page=100",
            callback=self.parse_variations,
            meta={
                "parent": {
                    "name": str(p.get("name") or ""),
                    "base_id": str(p.get("sku") or p.get("id")),
                    "categories": p.get("categories") or [],
                    "permalink": p.get("permalink") or "",
                    "is_in_stock": p.get("is_in_stock", True),
                    "labels": labels,
                }
            },
        )

    def parse_variations(self, response):
        try:
            variations = response.json()
        except ValueError:
            logger.warning(f"non-JSON variations at {response.url}")
            return
        if not isinstance(variations, list):
            return
        parent = response.meta["parent"]
        base_id = parent["base_id"]
        name = parent["name"]
        labels = parent["labels"]
        for v in variations:
            prices = v.get("prices") or {}
            raw = prices.get("price")
            if raw is None:
                continue
            value = self._rescale(prices, raw)
            label = labels.get(str(v.get("id"))) or self._label(v)
            vname = f"{name} - {label}" if label else name
            row_src = {
                "categories": v.get("categories") or parent["categories"],
                "permalink": v.get("permalink") or parent["permalink"],
                "is_in_stock": v.get("is_in_stock", parent["is_in_stock"]),
            }
            yield self._row(row_src, prices, f"{base_id}_{v.get('id')}", vname, value)
