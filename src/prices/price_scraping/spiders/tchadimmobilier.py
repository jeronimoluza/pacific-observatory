"""Tchad Immobilier -- https://tchadimmobilier.com/. N'Djamena property
portal on WooCommerce; the public Store API is open (no key, no
impersonation) and reports currency_code XAF with currency_minor_unit 0.

Not built on the shared _woo_base.py, for one reason: this source has to be
filtered, and the base has no hook for it. The unfiltered catalog is 84
listings dominated by property *sales* (Maisons en Vente 46, Terrains 21) at
5,000,000-50,000,000 XAF -- capital transactions with no COICOP leaf, which
must not enter a consumption price corpus. We pin the two rental categories
(100 "Maison a Louer", 107 "Appartements Meubles"); the Store API accepts
them as a comma-separated OR filter.

Two further filters, both measured rather than defensive:
  * `name` is empty on three of the nine rentals (unpublished drafts). One
    of them is priced 240,000,000 XAF -- a sale mis-filed under a rental
    category. An unnamed row is useless to any downstream consumer and this
    one would be a catastrophic "monthly rent", so empty names are dropped.
  * product id 159 "Black and White" (115 XAF) is the stock WooCommerce
    sample product, left behind in "Appartements Meubles". Dropped by id.

Page family: API -- the Store API is read directly and the /produit/<slug>
permalinks it returns are never fetched.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import scrapy

API = (
    "https://tchadimmobilier.com/wp-json/wc/store/v1/products"
    "?per_page=100&category=100,107"
)
# Stock WooCommerce sample product left in the Appartements Meubles category.
DEMO_PRODUCT_IDS = {159}
_TAG_RE = re.compile(r"<[^>]+>")


class TchadimmobilierSpider(scrapy.Spider):
    name = "tchadimmobilier"
    allowed_domains = ["tchadimmobilier.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(API, callback=self.parse_api)

    def parse_api(self, response):
        try:
            products = response.json()
        except ValueError:
            self.logger.warning(f"non-JSON response at {response.url}")
            return
        for p in products:
            if p.get("id") in DEMO_PRODUCT_IDS:
                continue
            name = html.unescape(_TAG_RE.sub("", p.get("name") or "")).strip()
            if not name:
                # Unpublished draft: no name, and at least one carries a
                # sale price mis-filed under a rental category.
                continue
            prices = p.get("prices") or {}
            raw = prices.get("price")
            if raw is None:
                continue
            minor = int(prices.get("currency_minor_unit") or 0)
            try:
                value = int(raw) / (10 ** minor)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            cats = [c.get("name") for c in (p.get("categories") or []) if c.get("name")]
            yield {
                "product_id": str(p.get("id")),
                "product_name": name[:500],
                "category": " / ".join(cats) or None,
                "price": f"{value:.2f}".rstrip("0").rstrip("."),
                "currency": prices.get("currency_code") or self.currency,
                "available": p.get("is_in_stock", True),
                "url": p.get("permalink"),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
