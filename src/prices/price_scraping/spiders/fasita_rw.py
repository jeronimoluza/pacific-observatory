"""Spider for Fasita (Rwanda) -- https://fasita.rw/.

React/Vite SPA (Kigali + Huye grocery/food delivery) backed by a plain JSON
API, no auth required. Verified live 2026-09-11: GET
https://fasita.rw/api/products -> 200, ~54KB JSON, a flat list of 137
products across Fruits/Food/Drinks/Home Care/Kitchen/Personal Care/Pharma/
Stationery -- no pagination, the whole catalog in one response (limit/
offset/page query params are accepted but ignored; always returns all 137).
Found via a Playwright network-capture pass -- the homepage itself is a
location-picker shell with no server-rendered catalog; every other
guessed endpoint gated behind /api/customer/me (401). Sample:
'Custard banana / apple banana (Kamara)' category=Fruits base_price=1500.00.
Currency RWF (matches countries.yaml; site is Rwanda-only, no explicit
currency field in the payload). PDP route /product/<id> returns 200 but is
the same client-rendered SPA shell for every id (no server-side content
differs) -- used only as a stable per-product permalink for dedup, not as
a fetchable page.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://fasita.rw/api/products"


class FasitaRwSpider(scrapy.Spider):
    name = "fasita_rw"
    allowed_domains = ["fasita.rw"]
    currency = "RWF"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        yield scrapy.Request(
            _API,
            callback=self.parse,
            headers={"Referer": "https://fasita.rw/", "Accept": "application/json"},
        )

    def parse(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        if not isinstance(products, list):
            return
        logger.info(f"{self.name}: count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("base_price")
            if price is None:
                continue
            product_id = str(p.get("id") or "")
            yield {
                "product_id": product_id,
                "product_name": str(p.get("name") or "").strip()[:500],
                "category": p.get("category") or None,
                "price": str(price),
                "currency": self.currency,
                "available": p.get("stock_status") == "in_stock",
                "url": f"https://fasita.rw/product/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
