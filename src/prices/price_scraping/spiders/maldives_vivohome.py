"""Scrape Vivo Home Maldives products from server-rendered Next.js state."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


logger = logging.getLogger(__name__)
BASE_URL = "https://www.vivohome.mv"


def parse_product(product: dict, scraped_at: str):
    product_id = str(product.get("id") or "").strip()
    name = " ".join(str(product.get("name") or "").split())
    slug = str(product.get("slug") or "").strip()
    raw_price = product.get("sale_price") or product.get("price")
    try:
        price = Decimal(str(raw_price))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not product_id or not name or not slug or price <= 0:
        return None
    tracked = bool(product.get("inventory_tracking"))
    quantity = product.get("inventory_quantity", product.get("inventory"))
    available = not bool(product.get("force_out_of_stock"))
    if tracked and quantity is not None:
        available = available and float(quantity) > 0
    return {
        "product_id": product_id,
        "product_name": name[:500],
        "category": product.get("category_name"),
        "price": format(price, "f"),
        "currency": "MVR",
        "country": "Maldives",
        "sector": "consumer_goods",
        "available": available,
        "url": f"{BASE_URL}/product/{slug}",
        "language": "en",
        "scraped_at_utc": scraped_at,
    }


class MaldivesVivohomeSpider(scrapy.Spider):
    name = "maldives_vivohome"
    allowed_domains = ["vivohome.mv", "www.vivohome.mv"]
    start_urls = [f"{BASE_URL}/products"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        raw = response.css("script#__NEXT_DATA__::text").get()
        if not raw:
            logger.warning("%s: no __NEXT_DATA__", self.name)
            return
        try:
            build_id = json.loads(raw)["buildId"]
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("%s: malformed build state", self.name)
            return
        yield scrapy.Request(
            f"{BASE_URL}/_next/data/{build_id}/products.json",
            callback=self.parse_data,
            headers={"Accept": "application/json"},
        )

    def parse_data(self, response):
        try:
            products = response.json()["pageProps"]["ssrProducts"] or []
        except (ValueError, KeyError, TypeError):
            logger.warning("%s: malformed products JSON", self.name)
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen_urls = set()
        for product in products:
            item = parse_product(product, scraped_at)
            if not item or item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            yield item
