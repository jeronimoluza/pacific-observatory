"""Spider for Dado.tj (Tajikistan) -- https://dado.tj/.

Dado.tj is a Dushanbe grocery e-commerce store on plain WordPress +
WooCommerce. Discovery lead (wave 4, bare hostname `dado.tj`, triage
AI_NOTES said "supermarket with app; web presence needs confirming" --
the web presence is real and needs no app).

Uses the unauthenticated WooCommerce Store API directly
(`/wp-json/wc/store/v1/products`) -- no Playwright, no curl_cffi
impersonation needed, plain `requests`-style GET clears with a 200 on the
default Scrapy downloader.

**Minor-unit trap**: the Store API's `prices.price` / `regular_price` /
`sale_price` fields are integer minor units, not decimals --
`currency_minor_unit` is 2, so divide by 100. Verified against the
storefront's own `price_html` rendering (WooCommerce's price widget shows
"12,30 CMH" for a raw `price` of `"1230"`).

`currency_symbol` on this store is the literal string "CMH", not the usual
"смн"/"c." abbreviation seen elsewhere -- a shop-admin display quirk.
`currency_code` is unambiguous: TJS.

**Catalogue is mostly unpriced**: of 391 products across 8 pages of 50, only
~44 (~11%) carry a non-zero price -- the rest are `"0"`, i.e. listed but not
price-tagged (out of stock / awaiting pricing). Per the mekkamarket.ro
convention (drop zero-price rows rather than emit them), zero/blank prices
are skipped here too.

Page family parsed: API only (spider never fetches an HTML page).

Test run 2026-09-06 (--max-items 5): passed, TJS prices in the 1-40 somoni
range, matching visible in-app pricing for the sampled SKUs (energy drinks,
snacks).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://dado.tj"
_API = _BASE + "/wp-json/wc/store/v1/products"
_PAGE_SIZE = 50
_MAX_PAGES = 10  # catalogue is ~391 products / 50 per page = 8 pages


class DadoTjSpider(scrapy.Spider):
    name = "dado_tj"
    allowed_domains = ["dado.tj"]
    currency = "TJS"
    language = "ru"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "DOWNLOAD_TIMEOUT": 60,
    }

    def start_requests(self):
        for page in range(1, _MAX_PAGES + 1):
            yield scrapy.Request(
                f"{_API}?per_page={_PAGE_SIZE}&page={page}",
                callback=self.parse_page,
                meta={"page": page},
            )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            products = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"dado_tj: JSON decode failed on page {page}")
            return
        if not products:
            logger.info(f"dado_tj: page {page} empty, stopping")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        for prod in products:
            prices = prod.get("prices") or {}
            raw_price = prices.get("price") or "0"
            try:
                minor_unit = int(prices.get("currency_minor_unit", 2))
                price_val = int(raw_price) / (10**minor_unit)
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue

            name = (prod.get("name") or "").strip()
            if not name:
                continue

            categories = prod.get("categories") or []
            category = " > ".join(c.get("name", "") for c in categories if c.get("name"))

            yield {
                "product_id": prod.get("id"),
                "product_name": name,
                "price": price_val,
                "currency": prices.get("currency_code") or self.currency,
                "category": category or None,
                "url": prod.get("permalink"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1

        logger.info(f"dado_tj: page={page} products={len(products)} yielded={yielded}")

        # Store API returns an empty list once past the last page.
        if len(products) < _PAGE_SIZE:
            logger.info(f"dado_tj: page {page} short ({len(products)} < {_PAGE_SIZE}), last page")
