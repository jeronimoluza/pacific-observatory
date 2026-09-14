"""Marc's Eatery Maun menu extractor using Wix's first-party page state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy


URL = "https://www.marcseatery.com/online-ordering"


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class BotswanaMarcsEateryMaunSpider(scrapy.Spider):
    name = "botswana_marcs_eatery_maun"
    allowed_domains = ["www.marcseatery.com", "marcseatery.com"]
    custom_settings = {"DOWNLOAD_DELAY": 0.5, "CONCURRENT_REQUESTS_PER_DOMAIN": 1}

    async def start(self):
        yield scrapy.Request(URL, callback=self.parse)

    def parse(self, response):
        seen: set[str] = set()
        for script in response.css("script::text").getall():
            if not script.lstrip().startswith("{"):
                continue
            try:
                root = json.loads(script)
            except json.JSONDecodeError:
                continue
            for item in walk(root):
                price = item.get("price")
                name = clean(item.get("name"))
                if not name:
                    continue
                item_id = str(item.get("id") or "")
                parent_key = item_id or name.lower()
                variants = item.get("priceVariants", {}).get("variants", [])
                for variant in variants:
                    variant_name = clean(variant.get("name"))
                    variant_price = variant.get("priceInfo", {}).get("price")
                    variant_id = str(variant.get("id") or "")
                    try:
                        amount = float(variant_price)
                    except (TypeError, ValueError):
                        continue
                    if not variant_name or amount <= 0:
                        continue
                    variant_key = variant_id or f"{parent_key}:{variant_name.lower()}:{amount}"
                    if variant_key in seen:
                        continue
                    seen.add(variant_key)
                    yield {
                        "product_id": f"marcs:{variant_key}",
                        "product_name": f"{name} - {variant_name}",
                        "price": str(amount),
                        "currency": "BWP",
                        "channel": "restaurant_menu",
                        "locality": "Maun, Botswana",
                        "url": f"{response.url}#item={quote(f'marcs:{variant_key}', safe='')}",
                        "language": "en",
                        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                if not isinstance(price, dict):
                    continue
                amount, currency = price.get("amount"), price.get("currency")
                if currency != "BWP" or not isinstance(amount, (int, float)) or amount <= 0:
                    continue
                key = item_id or f"{name.lower()}:{amount}"
                if key in seen:
                    continue
                seen.add(key)
                yield {
                    "product_id": f"marcs:{key}",
                    "product_name": name,
                    "price": str(amount),
                    "currency": currency,
                    "channel": "restaurant_menu",
                    "locality": "Maun, Botswana",
                    "url": f"{response.url}#item={quote(f'marcs:{key}', safe='')}",
                    "language": "en",
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
