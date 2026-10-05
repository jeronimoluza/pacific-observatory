"""Scrape Cokie's Cookery & Bar's weekly Freetown menu."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape

import scrapy


def clean(value):
    return " ".join(unescape(value or "").split())


def parse_menu(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for panel in response.css("div.menu-panel[data-panel]"):
        day = clean(panel.css("::attr(data-panel)").get()).lower()
        if not day:
            continue
        for section in panel.css("div.menu-category"):
            category = clean(section.css("h3::text").get()) or "menu"
            for item in section.css("div.menu-item[data-name][data-price]"):
                name = clean(item.css("::attr(data-name)").get())
                visible_price = clean(item.css("span.menu-item-price::text").get())
                if not name or not visible_price.lower().startswith("le "):
                    continue
                try:
                    price = Decimal(item.css("::attr(data-price)").get() or "0")
                except InvalidOperation:
                    continue
                if price <= 0:
                    continue
                identity = f"{day}|{category}|{name}"
                product_id = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:20]
                if product_id in seen:
                    continue
                seen.add(product_id)
                yield {
                    "product_id": product_id,
                    "product_name": f"{name} ({day.title()})"[:500],
                    "category": f"{category} / {day.title()}"[:500],
                    "price": format(price, "f"),
                    "currency": "SLE",
                    "country": "Sierra Leone",
                    "sector": "food_and_beverages",
                    "available": True,
                    "url": f"{response.url}#menu-{product_id}",
                    "language": "en",
                    "scraped_at_utc": scraped_at,
                }


class CokiesrestaurantSlSpider(scrapy.Spider):
    name = "cokiesrestaurant_sl"
    allowed_domains = ["cokiesrestaurant.com", "www.cokiesrestaurant.com"]
    start_urls = ["https://www.cokiesrestaurant.com/"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse(self, response):
        yield from parse_menu(response)
