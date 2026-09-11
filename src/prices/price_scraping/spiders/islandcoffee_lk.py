"""
Spider for Island Coffee — islandcoffee.lk, "Perfecting the art of
coffee since 1964".

`curl_cffi` TLS impersonation (chrome124/chrome120/safari17_0) returned
403; plain `requests` with no impersonation clears to 200 -- same
impersonation-is-the-cause pattern as ksuper_lk.

WooCommerce Store API, no auth: /wp-json/wc/store/v1/products?per_page=N
Confirmed 13 products total (X-WP-Total header) -- a thin but real
specialty-coffee catalog. currency_minor_unit=2 confirmed in the
payload (e.g. "23000" -> LKR 230.00 for "Island Coffee Powder").

Page family: API only — the spider never fetches an HTML page.

Verified live 2026-09-11: --max-items 100 run returned all 13 rows.
Sample: "Jaffna Coffee" LKR 300.00, "Cinnamon Coffee" LKR 250.00.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://islandcoffee.lk/wp-json/wc/store/v1/products"
PER_PAGE = 50
MAX_PAGES = 5  # safety cap; catalog is ~13 items


class IslandcoffeeLkSpider(scrapy.Spider):
    name = "islandcoffee_lk"
    allowed_domains = ["islandcoffee.lk"]
    currency = "LKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "ROBOTSTXT_OBEY": False,
        # Plain UA, no TLS impersonation -- see module docstring.
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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
            logger.warning(f"islandcoffee_lk: non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info(f"islandcoffee_lk: page={page} count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}?per_page={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, p: dict):
        prices = p.get("prices") or {}
        raw = prices.get("price")
        if raw is None:
            return None
        try:
            minor = int(prices.get("currency_minor_unit", 0) or 0)
            value = int(raw) / (10**minor) if minor else int(raw)
        except (TypeError, ValueError):
            value = raw
        if not value:
            return None
        cats = p.get("categories") or []
        cat = (
            " > ".join(
                c.get("name") for c in cats if isinstance(c, dict) and c.get("name")
            )
            or None
        )
        return {
            "product_id": str(p.get("sku") or p.get("id")),
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": cat,
            "price": str(value),
            "currency": prices.get("currency_code") or self.currency,
            "available": bool(p.get("is_in_stock", True)),
            "url": p.get("permalink") or "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
