"""
Spider for Express Market CM (https://expressmarketcm.com/) -- Cameroon
multi-vertical marketplace backed by a public PocketBase instance
(`/hcgi/platform/api/collections/...`).

The site fronts that API behind a bot-management challenge that blocks
curl_cffi impersonation -- `chrome124`, `chrome120`, and `safari17_0` all
return 403 with a "Just a moment..." JS-challenge page (confirmed
2026-09-01, `server: hcdn`). This is a real Chromium TLS/HTTP2 fingerprint
check, not a cookie gate: navigating a genuine Playwright chromium page
DIRECTLY to the API URL -- no homepage warm-up, no cookies set -- returns
200 every time in repeated tests, while curl_cffi with a matching
User-Agent 403s every time. Hence `extraction_pattern: scrapy_playwright`
(Tier 2), one Request per crawl.

Verified live 2026-09-01:
  GET https://expressmarketcm.com/hcgi/platform/api/collections/products/records
      ?page=1&perPage=250&expand=vendor_id
  -> 200, 203 total products / 195 vendors spanning many verticals
     (Alimentation, Pharmacie, Electronique, Mode, Restaurant, ...).

This spider does NOT scrape the full blended marketplace (that would be
channel=marketplace and non-food, duplicating the yorix_cm pattern
already on file for Cameroon). Instead it is scoped per rule 14 ("a
marketplace can be onboarded as its individual first-party merchants") to
the two genuine food-and-beverage vendor groups, selected via
`-a vendor_group=supermarket|bakery`:

  vendor_group=supermarket -> vendor "Yatch Center" (Bafoussam). Its own
    vendor `description` field (self-authored, not the unreliable `type`
    taxonomy) reads: "Courses et alimentation ... Boulangerie et
    patisserie ... Cave et boissons ... Detente et loisirs" -- a genuine
    general supermarket. 26 SKUs.
  vendor_group=bakery -> 6 vendors named "Boulangerie ...". The source's
    own vendor `type` field tags these the same as Yatch Center
    ("Supermarche"), which is unreliable (a boulangerie is not a
    supermarket) -- this spider instead groups by vendor NAME containing
    "boulangerie". 46 SKUs: bread/pastry items (Madeleine, Cake Chocolat,
    Cake citron) plus a general grocery shelf (milk, chocolate, whisky,
    mayonnaise, juice) -- typical of a Cameroonian neighbourhood bakery
    that also stocks packaged groceries.

Both groups are Bafoussam-only (verified against the full 203-row feed --
no Douala/Yaounde rows for either group; one unrelated vendor elsewhere in
the full catalog listed "Brazzaville", out of scope for these two groups).

Prices are integer XAF (e.g. 1425 for 1L palm oil) -- matches
countries.yaml. The API returns plain JSON numbers, not
space-thousands-separated strings, so no XAF string-parsing trap applies
here.

Product URLs are synthesized from the frontend's real per-product route
(confirmed present in the rendered homepage: `href="/product/<id>"`), so
each row is independently re-fetchable and DuplicationPipeline's
url-dedup (rule 9) sees a unique url per row.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


def _extract_json(response):
    """Parse the PocketBase JSON payload out of a scrapy-playwright response.

    Chromium wraps a `content-type: application/json` navigation in
    `<html><body><pre>{...}</pre></body></html>` rather than handing back
    the raw body, so `response.json()` fails on this site every time --
    confirmed live 2026-09-01. Pull the `<pre>` text first; fall back to
    the raw response text for robustness if that markup ever changes.
    """
    pre_text = response.css("pre::text").get()
    raw = pre_text if pre_text is not None else response.text
    return json.loads(raw)


_PRODUCTS_URL = (
    "https://expressmarketcm.com/hcgi/platform/api/collections/products/records"
    "?page=1&perPage=250&expand=vendor_id"
)
_CATEGORIES_URL = (
    "https://expressmarketcm.com/hcgi/platform/api/collections/categories/records"
    "?page=1&perPage=200"
)

_SUPERMARKET_VENDOR_NAMES = {"Yatch Center"}


class ExpressMarketCmSpider(scrapy.Spider):
    name = "express_market_cm"
    allowed_domains = ["expressmarketcm.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, vendor_group=None, **kwargs):
        super().__init__(*args, **kwargs)
        if vendor_group not in ("supermarket", "bakery"):
            raise ValueError(
                "express_market_cm requires -a vendor_group=supermarket|bakery"
            )
        self.vendor_group = vendor_group
        self._categories: dict[str, str] = {}

    async def start(self):
        yield scrapy.Request(
            _CATEGORIES_URL,
            callback=self.parse_categories,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
            },
        )

    def parse_categories(self, response):
        try:
            data = _extract_json(response)
        except (ValueError, json.JSONDecodeError):
            logger.warning(
                f"express_market_cm: non-JSON categories response at {response.url}"
            )
            data = {}
        for c in data.get("items") or []:
            cid = c.get("id")
            if cid:
                self._categories[cid] = c.get("name")
        logger.info(f"express_market_cm: loaded {len(self._categories)} categories")
        yield scrapy.Request(
            _PRODUCTS_URL,
            callback=self.parse_products,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
            },
        )

    def _vendor_matches(self, vendor: dict) -> bool:
        name = (vendor.get("name") or "").strip()
        is_bakery = "boulangerie" in name.lower()
        if self.vendor_group == "bakery":
            return is_bakery
        # supermarket: named allowlist, explicitly excludes bakeries even
        # though the source's own vendor `type` field tags them the same.
        return name in _SUPERMARKET_VENDOR_NAMES and not is_bakery

    def parse_products(self, response):
        try:
            data = _extract_json(response)
        except (ValueError, json.JSONDecodeError):
            logger.warning(
                f"express_market_cm: non-JSON products response at {response.url}"
            )
            return
        items = data.get("items") or []
        logger.info(f"express_market_cm: {len(items)} total products in feed")
        scraped_at = datetime.now(timezone.utc).isoformat()
        n_yielded = 0
        for it in items:
            vendor = (it.get("expand") or {}).get("vendor_id") or {}
            if not self._vendor_matches(vendor):
                continue
            price = it.get("price")
            pid = it.get("id")
            name = (it.get("name") or "").strip()
            if price is None or not name or not pid:
                continue
            category = self._categories.get(it.get("category_id"))
            stock = it.get("stock")
            yield {
                "product_id": str(pid),
                "product_name": name,
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": (stock is None) or (stock > 0),
                "url": f"https://expressmarketcm.com/product/{pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            n_yielded += 1
        logger.info(f"express_market_cm[{self.vendor_group}]: yielded {n_yielded} rows")
