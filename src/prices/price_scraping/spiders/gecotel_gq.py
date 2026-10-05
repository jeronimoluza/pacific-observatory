"""
Gecotel tienda (Equatorial Guinea) -- https://tienda.gecotel.post/. Small
PHP shop run by the national telco/post operator (electronics, stationery,
accessories). Every listing page embeds a schema.org ItemList JSON-LD with
name, absolute product URL, price and priceCurrency (XAF), so the spider
reads that block and never fetches a PDP. Enumeration is the category
filter (?categoria=N); the unfiltered /tienda.php page is also read.
Verified 2026-10-05: tienda.php returns 12 items, categoria=2 returns 11,
categoria=1 returns 2, categoria=3 returns 1 (distinct sets).
"""

import json
import re

import scrapy

_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_ID_RE = re.compile(r"[?&]id=(\d+)")
BASE = "https://tienda.gecotel.post/tienda.php?lang=es"
CATEGORY_IDS = range(1, 13)


class GecotelGqSpider(scrapy.Spider):
    name = "gecotel_gq"
    allowed_domains = ["tienda.gecotel.post"]
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(BASE, callback=self.parse_listing, meta={"cat": None})
        for c in CATEGORY_IDS:
            yield scrapy.Request(
                f"{BASE}&categoria={c}",
                callback=self.parse_listing,
                meta={"cat": str(c)},
            )

    def parse_listing(self, response):
        for block in _LD_RE.findall(response.text):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if data.get("@type") != "ItemList":
                continue
            for el in data.get("itemListElement", []):
                item = el.get("item") or {}
                offer = item.get("offers") or {}
                url = item.get("url")
                id_m = _ID_RE.search(url or "")
                try:
                    price = float(offer.get("price"))
                except (TypeError, ValueError):
                    continue
                if not (item.get("name") and id_m) or price <= 0:
                    continue
                yield {
                    "product_id": id_m.group(1),
                    "product_name": item["name"][:500],
                    "category": response.meta["cat"],
                    "price": str(price),
                    "currency": offer.get("priceCurrency") or "XAF",
                    "available": "InStock" in (offer.get("availability") or ""),
                    "url": url,
                    "language": self.language,
                }
