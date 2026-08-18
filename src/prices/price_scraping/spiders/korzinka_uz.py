"""
Spider for Korzinka (Uzbekistan) — https://www.korzinka.uz.

The customer-facing site sits behind a Cloudflare managed challenge (curl and
even bare requests to robots.txt/manifest.json 403 with a "Just a moment..."
Turnstile page), but the product data itself lives on a separate,
un-gated subdomain: catalog.korzinka.uz/api/catalogs/categories/ — a single
public JSON endpoint (no auth, no challenge) that returns the site's curated
homepage category sections with full nested product objects (name, category,
weight/pack size, current + pre-discount price). Endpoint discovered via the
open-source Flutter client github.com/professorDeveloper/Korzinka-Texnomart-
Full-Api (lib/core/api/karzinka_api.dart: `karzinkaCategorys()`).
Re-verified live 2026-08-06: GET -> HTTP 200, 458KB, 10 categories, 322
unique products. Sample: 'Виноград Шохона Узб. вес' 19 990 UZS (1кг);
'НАПИТОК COCA COLA П/Б 1,5Л' 24 790 UZS. No deeper category-tree/pagination
route was found (a guessed .../categories/tree 500s; per-category product
routes 404); this is a curated cross-category slice, not the full storewide
catalog, but every row is a real priced SKU.
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://catalog.korzinka.uz/api/catalogs/categories/"


class KorzinkaUzSpider(scrapy.Spider):
    name = "korzinka_uz"
    allowed_domains = ["catalog.korzinka.uz"]
    currency = "UZS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            _URL, callback=self.parse_page, headers={"Accept": "application/json"}
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning("korzinka_uz: non-JSON response at %s", response.url)
            return
        categories = payload.get("data") or []
        seen_ids: set[str] = set()
        for cat in categories:
            cat_name = html.unescape(cat.get("title_ru") or cat.get("title_en") or "")
            for p in cat.get("products") or []:
                pid = str(p.get("id") or "")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                item = self._item(p, cat_name)
                if item:
                    yield item

    def _item(self, p: dict, cat_name: str):
        name = html.unescape((p.get("title_ru") or p.get("title") or "").strip())
        if not name:
            return None
        weight = (p.get("weight_param") or "").strip()
        if weight and weight.lower() not in name.lower():
            name = f"{name} {weight}"
        prices = p.get("prices") or {}
        raw_price = prices.get("actual_price")
        if raw_price is None:
            return None
        try:
            price = float(
                str(raw_price).replace(" ", "").replace("\xa0", "").replace(",", ".")
            )
        except ValueError:
            return None
        pid = str(p.get("id"))
        return {
            "product_id": pid,
            "product_name": name[:500],
            "category": cat_name or None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://catalog.korzinka.uz/product/{pid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
