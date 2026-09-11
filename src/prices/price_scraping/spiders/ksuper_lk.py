"""
Super K Online Grocery (Sri Lanka) — ksuper-shop.com.

`server: hcdn` 403s under curl_cffi TLS impersonation (all three
profiles) but clears to 200 with plain `requests`, no impersonation and
no special headers -- the impersonated JA3 fingerprint is on a
denylist here, per the general hcdn-cluster finding (impersonation is
the cause of the block, not the cure).

Not a backend-driven storefront at all: the whole catalog is a static
JS array (`const products = [...]`) inline in /data.js, referenced from
a client-rendered single-page shell (categories/cart handled by
onclick="navigateTo(...)"/"filterAndNavigate(...)" JS, "Keells Style"
per an HTML comment). Small, hand-maintained catalog (100 items, some
image fields point at Unsplash stock photos where a real product photo
is missing) rather than an inventory-system-backed store -- still real
LKR prices for real Sri Lankan grocery items (e.g. "Samba Rice 1kg"
LKR 230, "Sugar 1kg" LKR 285).

7 categories total: Dry Rations, Snacks, Beverages, Personal Care, Home
Care, Canned Foods, Sauces & Oils -- food-dominant (4-5 of 7), so
channel: convenience (small hand-run grocery, not a full supermarket).

Object literals in the JS use unquoted keys (not strict JSON), so this
parses each `{ id: N, name: "...", ..., price: N, ... }` entry with a
regex rather than json.loads.

Page family: single static asset (/data.js), no pagination, no PDP.

Verified live 2026-09-11: --max-items 100 run against /data.js
produced 100 rows (whole catalog in one fetch). Sample: "Samba Rice
1kg" LKR 230.00, "Dhal 1kg" LKR 320.00.
"""

import re
from datetime import datetime, timezone

import scrapy

_ITEM_RE = re.compile(
    r'\{\s*id:\s*(?P<id>\d+),\s*name:\s*"(?P<name>[^"]+)"'
    r'(?:,\s*nameSi:\s*"[^"]*")?'
    r',\s*category:\s*"(?P<category>[^"]+)"'
    r',\s*price:\s*(?P<price>[\d.]+)',
)


class KsuperLkSpider(scrapy.Spider):
    name = "ksuper_lk"
    allowed_domains = ["ksuper-shop.com"]
    currency = "LKR"
    language = "en"
    start_urls = ["https://ksuper-shop.com/data.js"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        # curl_cffi-style TLS impersonation is denylisted on this host
        # (server: hcdn 403 on all profiles); use a plain Chrome UA with
        # no impersonation, which clears it.
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for m in _ITEM_RE.finditer(response.text):
            try:
                price = float(m.group("price"))
            except ValueError:
                continue
            if price <= 0:
                continue
            yield {
                "product_id": m.group("id"),
                "product_name": m.group("name").strip(),
                "price": price,
                "currency": self.currency,
                "category": m.group("category").strip(),
                # No real per-product page exists (client-rendered SPA with
                # no routable PDP) -- DuplicationPipeline dedups on
                # item["url"], so a shared homepage URL across all rows
                # would collapse the whole catalog to 1 row. Synthesize a
                # unique URL per product id instead.
                "url": f"https://ksuper-shop.com/?product={m.group('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
