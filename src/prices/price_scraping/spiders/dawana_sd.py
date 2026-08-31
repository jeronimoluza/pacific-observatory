"""Dawana (Sudan) -- https://dawana.online/, an online pharmacy.

Standard WooCommerce Store API (/wp-json/wc/store/v1/products), but the host
sits behind an "hcdn" bot-wall that flat-403s any curl_cffi impersonation
(same wall blocks zaad.delivery). A real Playwright-driven Chromium with a
desktop UA navigating straight to the API URL passes -- no separate
challenge-solving step needed, unlike sites that require visiting the HTML
page first. Response body is a bare JSON array wrapped in Chromium's default
`<pre>` viewer for a non-HTML content-type; unwrap and json.loads it.

Small catalog (56 products at per_page=100, single page) -- SDG minor_unit=2
so prices divide by 100 (e.g. raw "550000" -> 5,500.00 SDG for Imodium).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

BASE_URL = "https://dawana.online/wp-json/wc/store/v1/products"
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PER_PAGE = 100
MAX_PAGES = 50

_PRE_RE = re.compile(r"<pre[^>]*>(.*)</pre>", re.S)


class DawanaSdSpider(scrapy.Spider):
    name = "dawana_sd"
    allowed_domains = ["dawana.online"]
    currency = "SDG"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2,
    }

    def _page_meta(self, page: int) -> dict:
        return {
            "playwright": True,
            "playwright_context_kwargs": {"user_agent": DESKTOP_UA},
            "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
            "playwright_page_methods": [PageMethod("wait_for_timeout", 5000)],
            "page": page,
        }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}?per_page={PER_PAGE}&page=1",
            callback=self.parse_page,
            dont_filter=True,
            meta=self._page_meta(1),
        )

    def parse_page(self, response):
        page = response.meta["page"]
        m = _PRE_RE.search(response.text)
        raw = m.group(1) if m else response.text
        try:
            products = json.loads(raw)
        except ValueError:
            logger.warning(f"dawana_sd: non-JSON response at page={page}")
            return
        if not isinstance(products, list) or not products:
            return
        logger.info(f"dawana_sd page={page} count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE_URL}?per_page={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                dont_filter=True,
                meta=self._page_meta(nxt),
            )

    def _item(self, p: dict):
        prices = p.get("prices") or {}
        raw_price = prices.get("price")
        if raw_price is None:
            return None
        try:
            minor = int(prices.get("currency_minor_unit", 0) or 0)
            value = int(raw_price) / (10**minor) if minor else int(raw_price)
        except (TypeError, ValueError):
            value = raw_price
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
