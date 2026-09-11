"""JubaSquare (South Sudan) -- https://www.jubasquare.com/marketplace.

React SPA ("Juba trusted marketplace -- shop retail, wholesale and food,
all in one place", per /manifest.json) built by L.T.G Enterprise. The
homepage never renders products server-side, but the bundle
(/static/js/main.<hash>.js) references a same-origin, unauthenticated JSON
endpoint: GET /api/products (Accept: application/json). No pagination is
honoured -- ?page=, ?offset=, ?skip= are all ignored and return the same
first-40 default; ?limit=200 (or higher) returns the FULL catalog in one
response. MEASURED 2026-09-11: 94 distinct product ids at limit=200, and
limit=1000 still returns exactly 94 -- confirmed this is the whole catalog,
not a truncated page. Enumerability is therefore total-count-confirmed
rather than page1-vs-page2 (there is only one real page).

Catalog mix (94 items): ~64 FMCG food/beverage/household items (rice,
beans, wheat flour, sugar, tea, milk powder, tomato paste, cooking oil/
margarine, peanut butter, sardines, chocolate/confectionery, bottled water,
sodas, fruit juice, beer/wine/spirits) tagged either "FMCG Wholesale >
Beverage Wholesale" or with no category label at all (category is null for
most of the food items despite being clearly food by name -- the site's own
taxonomy is incomplete, left to the repo's classifier instead of trusting
the raw category field), plus ~29 non-food B2B items (electronics/machinery
import-distribution, commercial kitchen equipment, one shampoo SKU). Mixed
retail/wholesale: shop_kind is "retail" or null, mode is "wholesale" for
many rows with min_order_qty/pricing_tiers for bulk breaks -- the base
price_usd field is used as-is per listing (already the site's own headline
price for that specific SKU/pack-size row; bulk-tier prices in
pricing_tiers are NOT emitted as separate rows).

Currency: native field is price_usd (site is USD-denominated) with a
per-item exchange_rate_ssp (measured 7800.0 SSP/USD on every row sampled)
supplied by the site itself -- NOT computed here. Per the onboarding brief's
instruction to flag rather than silently accept/reject a genuine non-local
-currency retailer: this is a real Juba-facing wholesale/retail marketplace
that happens to price natively in USD, consistent with South Sudan's severe
SSP volatility -- reported here as currency: USD, reading straight from
the payload rather than converting via the embedded FX rate.

No stable per-product URL exists in the payload (a client-side React route,
never a server path) -- constructs a synthetic but stable identifier URL
from the product's uuid id, following the same pattern already used for
busiquip_sz.py in this repo: the url exists to satisfy
DuplicationPipeline's url-based dedup, not to be a fetchable PDP.
"""

from __future__ import annotations

from datetime import datetime, timezone

import scrapy

API_URL = "https://www.jubasquare.com/api/products?limit=1000"


class JubasquareSsSpider(scrapy.Spider):
    name = "jubasquare_ss"
    allowed_domains = ["jubasquare.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(
            API_URL,
            callback=self.parse_products,
            headers={"Accept": "application/json"},
        )

    def parse_products(self, response):
        try:
            items = response.json()
        except Exception:
            return
        for it in items:
            price = it.get("price_usd")
            try:
                if price is None or float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            pid = it.get("id")
            if not pid:
                continue
            yield {
                "product_id": pid,
                "product_name": (it.get("name") or "").strip()[:500],
                "category": it.get("category") or None,
                "price": price,
                "currency": self.currency,
                "available": (it.get("stock") or 0) > 0,
                "url": f"https://www.jubasquare.com/marketplace/product/{pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
