"""
MasterMarket (Ireland) — https://www.mastermarketapp.com/.

Real-price aggregator, not a survey publisher: it scrapes and republishes
live per-store shelf prices from Ireland's five biggest grocery chains
(Tesco, Aldi, Lidl, SuperValu, Dunnes Stores). Each price row carries a
`scraper_url` pointing at the actual retailer product page it was pulled
from, so this counts as retailer-sourced SKU data, not a cost-of-living
index (unlike numbeo/expatistan/livingcost, which never count).

Confirmed live 2026-08-31 via a Next.js chunk (app/page-*.js) that calls
`https://api.mastermarketapp.com`. That backend is a public FastAPI service
exposing its schema at `/openapi.json` (also serves interactive `/docs`):

  GET /api/products-public/sitemap-ids   -> {"ids": [int, ...]}   ALL product
                                             ids in one call (8,668 on the
                                             day this was written).
  GET /api/products-public/{product_id}  -> product detail incl.
                                             `recent_prices`: a list of
                                             {price, store_name, currency,
                                             scraper_url, promotion_type,
                                             has_clubcard_price, ...} — one
                                             entry per chain currently
                                             carrying that SKU.

`price` is already the price a shopper would pay right now at that chain
(clubcard/multi-buy price substituted in when active — `has_clubcard_price`
flags it). About half the ids have an empty `recent_prices` (delisted /
stale) and are skipped — matches the site's own "8,089 products / 4,120
active prices" framing in its own freshness endpoint. category comes from
the product detail's own taxonomy string (e.g. "Fresh Food / Milk, Butter &
Eggs / Fresh Milk"). Each (product, store) price row is emitted once,
keyed by MasterMarket's own price-observation id, with `url` pointing at
the underlying retailer's page (avoids DuplicationPipeline url-collisions
across chains for the same generic product).

No auth, no WAF/TLS-fingerprint gate (plain `urllib` gets 200), so no
curl_cffi impersonation is required for scrapy's own downloader. Full
catalog walk is ~8,700 requests against the detail endpoint; a generous
`timeout:` is set in the YAML.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://api.mastermarketapp.com/api/products-public"


class MastermarketIeSpider(scrapy.Spider):
    name = "mastermarket_ie"
    allowed_domains = ["api.mastermarketapp.com"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.05,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{API_BASE}/sitemap-ids",
            callback=self.parse_ids,
            errback=self.errback,
        )

    def parse_ids(self, response):
        data = response.json()
        ids = data.get("ids") or []
        logger.info(f"{self.name}: sitemap-ids returned {len(ids)} product ids")
        for pid in ids:
            yield scrapy.Request(
                f"{API_BASE}/{pid}",
                callback=self.parse_product,
                errback=self.errback,
                meta={"pid": pid},
                dont_filter=True,
            )

    def parse_product(self, response):
        try:
            product = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        name = (product.get("display_name") or product.get("name") or "").strip()
        category = product.get("category")
        if not name:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        pid = product.get("id") or response.meta["pid"]
        for entry in product.get("recent_prices") or []:
            price = entry.get("price")
            if price is None:
                continue
            price_id = entry.get("id")
            store = (entry.get("store_name") or "unknown").strip()
            url = entry.get("scraper_url") or (
                f"https://www.mastermarketapp.com/products/{pid}#{store}-{price_id}"
            )
            yield {
                "product_id": f"{pid}-{price_id}",
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": entry.get("currency") or self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
