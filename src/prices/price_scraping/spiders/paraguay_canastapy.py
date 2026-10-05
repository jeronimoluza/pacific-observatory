"""Scrape merchant-attributed offers from CanastaPY's public comparison API."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

import scrapy


QUERIES = (
    "arroz",
    "leche",
    "aceite",
    "pan",
    "carne",
    "shampoo",
    "detergente",
    "pañal",
    "cafe",
    "papel higienico",
)


class ParaguayCanastapySpider(scrapy.Spider):
    name = "paraguay_canastapy"
    allowed_domains = ["canastapy.com", "www.canastapy.com"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.25}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_offers: set[str] = set()

    async def start(self):
        for query in QUERIES:
            url = f"https://www.canastapy.com/api/search?q={quote(query)}&limit=40"
            yield scrapy.Request(
                url,
                headers={"Accept": "application/json", "Referer": "https://www.canastapy.com/"},
                callback=self.parse,
            )

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for offer in (response.json().get("rows") or []):
            product_id = str(offer.get("product_id") or "").strip()
            store_id = str(offer.get("store_id") or "").strip()
            store_name = " ".join(str(offer.get("store_name") or "").split())
            name = " ".join(str(offer.get("name") or "").split())
            url = str(offer.get("product_url") or "").strip()
            try:
                price = int(offer.get("price_gs") or 0)
            except (TypeError, ValueError):
                continue
            offer_id = f"{product_id}:{store_id}"
            if not (product_id and store_id and store_name and name and url and price > 0):
                continue
            if offer_id in self.seen_offers:
                continue
            self.seen_offers.add(offer_id)
            row = {
                "product_id": offer_id,
                "product_name": f"{name} - {store_name}"[:500],
                "category": str(offer.get("category") or "consumer goods")[:200],
                "price": str(price),
                "currency": "PYG",
                "country": "Paraguay",
                "sector": "consumer_goods",
                "available": bool(offer.get("in_stock", False)),
                "url": url,
                "language": "es",
                "scraped_at_utc": scraped_at,
            }
            observed_at = str(offer.get("scraped_at") or "")
            if len(observed_at) >= 10:
                row["price_date"] = observed_at[:10]
            yield row
