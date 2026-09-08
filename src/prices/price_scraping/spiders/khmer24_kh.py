"""
Khmer24 (Cambodia) -- https://www.khmer24.com/.

General classifieds marketplace (cars, real estate, jobs, consumer goods).
The public-facing site is a Nuxt SPA -- curl_cffi gets a hydration-free
shell with no listing HTML -- but the app's own data API at
https://api.khmer24.com has no anti-bot at all and returns clean JSON:

    GET /posts?category=<id>&offset=<n>  -> {"limit": 30, "data": [...]}
    GET /categories                      -> full category tree

`offset=` paginates with disjoint pages (confirmed: offsets 0/30/60/90 on
category=67 returned 120 distinct ids); `page=` does NOT (same 30 rows
regardless of page number) -- use offset only.

Previously recorded blocked (2026-06-10: "HTTP 403 + Cloudflare Turnstile
challenge page on curl with realistic Chrome UA"). Re-probed 2026-09-06:
that was a bare-curl TLS-handshake artifact -- curl_cffi with any of
chrome124/chrome120/chrome131/safari17_0/firefox133 clears the homepage at
200. The real blocker (SPA hydration, not anti-bot) is bypassed entirely by
hitting the API instead of the rendered page.

Scope: the full category tree (162 nodes) is mostly jobs and services with
no price field. Walks a curated set of consumer-goods leaf categories only
-- phones, laptops, cameras, home appliances, consumer electronics, smart
watches, furniture, kitchenware, fashion -- so the spider emits genuine
priced listings rather than job posts and null-price "Lost & Found" ads.

CAVEAT: these are individual sellers' secondhand-goods asking prices, not
a retailer's posted new-goods price -- closer in kind to a real-estate
listing spider's asking rents than to a supermarket SKU feed. Prices carry
occasional seller-set discounts (a `discount.sale_price` alongside the
listed `price`); this spider emits the sale price when present since that
is what a buyer would actually pay. No explicit currency field in the
payload; sampled electronics prices ($300-1400 for phones) are
unambiguously USD, matching the same dual-currency convention documented
for niront.yaml (also KH, also USD, against a KHR countries.yaml default).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

# Consumer-goods leaf categories only -- excludes jobs (parent=2), real
# estate for sale, "Lost & Found", "Information & Guide", and other
# non-priced or non-consumption listings.
_CATEGORY_IDS = {
    61: "Phones",
    50: "Laptops",
    53: "Cameras & camcorders",
    52: "Home appliances",
    64: "Consumer Electronics",
    193: "Smart Watches",
    121: "Phone Accessories",
    170: "Other Furniture",
    171: "Kitchenware",
    62: "Women's Fashion",
    207: "Men's Fashion",
}

PER_PAGE = 30
MAX_OFFSET = 300  # safety cap: 10 pages/category


class Khmer24KhSpider(scrapy.Spider):
    name = "khmer24_kh"
    allowed_domains = ["api.khmer24.com"]
    currency = "USD"
    language = "km"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        for cat_id, cat_name in _CATEGORY_IDS.items():
            yield scrapy.Request(
                self._url(cat_id, 0),
                callback=self.parse_page,
                meta={"category_id": cat_id, "category_name": cat_name, "offset": 0},
            )

    @staticmethod
    def _url(category_id: int, offset: int) -> str:
        return f"https://api.khmer24.com/posts?category={category_id}&offset={offset}"

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"non-JSON response at {response.url}")
            return
        rows = payload.get("data") or []
        category_id = response.meta["category_id"]
        category_name = response.meta["category_name"]
        offset = response.meta["offset"]
        logger.info(f"khmer24_kh category={category_name} offset={offset} count={len(rows)}")

        for entry in rows:
            item = self._item(entry, category_name)
            if item:
                yield item

        if len(rows) >= PER_PAGE and offset + PER_PAGE < MAX_OFFSET:
            nxt = offset + PER_PAGE
            yield scrapy.Request(
                self._url(category_id, nxt),
                callback=self.parse_page,
                meta={"category_id": category_id, "category_name": category_name, "offset": nxt},
            )

    def _item(self, entry: dict, category_name: str):
        data = entry.get("data") or {}
        title = data.get("title")
        if not title:
            return None
        discount = data.get("discount") or {}
        raw_price = discount.get("sale_price", data.get("price"))
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        post_id = data.get("id")
        return {
            "product_id": str(post_id) if post_id else None,
            "product_name": str(title).strip()[:500],
            "price": str(price),
            "currency": self.currency,
            "category": category_name,
            "url": f"https://www.khmer24.com/en/p/{post_id}" if post_id else None,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
