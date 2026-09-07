"""Carada Brunei automotive parts Inertia storefront catalog."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urljoin

import scrapy


_PRICE_SCALE = Decimal("10000")


def _bnd_price(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value)) / _PRICE_SCALE
    except (InvalidOperation, ValueError):
        return None
    return format(amount.normalize(), "f")


def _has_stock(value: object) -> bool:
    if value in (None, ""):
        return True
    try:
        return Decimal(str(value)) > 0
    except (InvalidOperation, ValueError):
        return True


class CaradaBnSpider(scrapy.Spider):
    name = "carada_bn"
    allowed_domains = ["carada.online"]
    start_urls = ["https://carada.online/shop?promo=true"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    def parse(self, response):
        page_blob = response.css("#app::attr(data-page)").get()
        if not page_blob:
            return
        page = json.loads(html.unescape(page_blob))
        products = page.get("props", {}).get("products", {}).get("data", [])
        scraped_at = datetime.now(timezone.utc).isoformat()

        for product in products:
            slug = product.get("slug")
            base_url = urljoin(response.url, f"/product/{slug}") if slug else response.url
            category = product.get("category", {}).get("name") or "Automotive parts"
            product_available = product.get("stock_status", "").lower() != "out of stock"
            options = product.get("sub_options") or []
            yielded_variant = False

            for group in options:
                group_title = group.get("title") or "Option"
                for option in group.get("options") or []:
                    price = _bnd_price(option.get("price_adjustment"))
                    if not price:
                        continue
                    variant = option.get("value")
                    item_code = option.get("item_code")
                    option_url = (
                        f"{base_url}?item_code={quote(str(item_code))}"
                        if item_code
                        else f"{base_url}?option={quote(str(variant))}"
                    )
                    yielded_variant = True
                    yield {
                        "product_id": item_code or f"{product.get('id')}:{variant}",
                        "product_name": f"{product.get('name')} - {group_title}: {variant}"[:500],
                        "category": category,
                        "price": price,
                        "currency": "BND",
                        "available": product_available and _has_stock(option.get("stock")),
                        "url": option_url,
                        "language": "en",
                        "scraped_at_utc": scraped_at,
                    }

            if not yielded_variant:
                price = _bnd_price(product.get("price"))
                if not price:
                    continue
                yield {
                    "product_id": str(product.get("id") or slug or base_url),
                    "product_name": str(product.get("name"))[:500],
                    "category": category,
                    "price": price,
                    "currency": "BND",
                    "available": product_available and _has_stock(product.get("stock")),
                    "url": base_url,
                    "language": "en",
                    "scraped_at_utc": scraped_at,
                }
