"""Scrape dated local retail-price bulletin rows from Nashrah Libya."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import scrapy


def clean(values):
    return " ".join(" ".join(values).split())


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for slide in response.css("div.swiper-slide"):
        category = clean(slide.css("span.category-title-main::text").getall())
        date = clean(slide.css("span.date-badge::text").getall())
        for row in slide.css("tbody tr"):
            name = clean(row.css("span.product-name::text").getall())
            company = clean(row.css("span.product-company::text").getall())
            cells = row.css("td")
            unit = clean(cells[1].css("::text").getall()) if len(cells) > 1 else ""
            raw_price = clean(row.css("span.price-val::text").getall())
            if not name or not raw_price:
                continue
            try:
                price = Decimal(raw_price.replace(",", ""))
            except InvalidOperation:
                continue
            if price <= 0:
                continue
            identity = "|".join((category, name, company, unit))
            product_id = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:20]
            if product_id in seen:
                continue
            seen.add(product_id)
            label = name
            if company:
                label += f" - {company}"
            if unit:
                label += f" ({unit})"
            yield {
                "product_id": product_id,
                "product_name": label[:500],
                "category": f"{category} | bulletin {date}" if date else category,
                "price": format(price, "f"),
                "currency": "LYD",
                "country": "Libya",
                "sector": "consumer_goods",
                "available": True,
                "url": f"{response.url}#row={quote(product_id)}",
                "language": "ar",
                "scraped_at_utc": scraped_at,
            }


class LibyaNashrahSpider(scrapy.Spider):
    name = "libya_nashrah"
    allowed_domains = ["nashrah.ly", "www.nashrah.ly"]
    start_urls = ["https://nashrah.ly/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
