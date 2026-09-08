"""
Spider for Tchitunga -- https://tchitunga.com/ ("plate-forme de services et
marche en ligne pour la diaspora congolaise" -- Congo Republic diaspora
grocery/marketplace, same care-package model as market242_cg).

Confirmed live 2026-09-06. WordPress/WooCommerce; the WooCommerce Store
API (`/wp-json/wc/store/v1/products`) is open, no auth, no anti-bot --
127 products total per `X-WP-Total`. Standard `scrapy_api` JSON pagination
(`per_page=50&page=N`).

MINOR-UNIT TRAP: `prices.price` is an INTEGER MINOR UNIT, not a decimal --
divide by `10 ** prices.currency_minor_unit` (confirmed
currency_minor_unit=2 throughout: raw "8000" -> 80.00, raw "189" -> 1.89).
Verified against `price_html` (not scraped, just eyeballed) for a spot
check before trusting the divide.

CURRENCY CAVEAT: prices.currency_code is EUR, not XAF (Congo Republic's
currency per countries.yaml) -- same diaspora-care-package caveat as
market242_cg: a buyer abroad pays in EUR for delivery inside Congo.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://tchitunga.com"
_API_URL = f"{_BASE}/wp-json/wc/store/v1/products"
_PAGE_SIZE = 50
MAX_PAGES = 20  # safety cap; site has 127 products at fetch time


class TchitungaCgSpider(scrapy.Spider):
    name = "tchitunga_cg"
    allowed_domains = ["tchitunga.com"]
    currency = "EUR"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_API_URL}?per_page={_PAGE_SIZE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            products = response.json()
        except ValueError:
            logger.warning("tchitunga_cg: non-JSON response on page %s", page)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            prices = p.get("prices") or {}
            raw_price = prices.get("price")
            minor_unit = prices.get("currency_minor_unit", 2)
            name = (p.get("name") or "").strip()
            if not name or raw_price in (None, ""):
                continue
            try:
                price = float(raw_price) / (10 ** int(minor_unit))
            except (TypeError, ValueError):
                continue
            categories = p.get("categories") or []
            category = categories[0]["name"] if categories else None

            yield {
                "product_id": p.get("id"),
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": prices.get("currency_code", self.currency),
                "available": bool(p.get("is_in_stock", True)),
                "url": p.get("permalink"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if len(products) >= _PAGE_SIZE and page < MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                f"{_API_URL}?per_page={_PAGE_SIZE}&page={next_page}",
                callback=self.parse_page,
                meta={"page": next_page},
            )
