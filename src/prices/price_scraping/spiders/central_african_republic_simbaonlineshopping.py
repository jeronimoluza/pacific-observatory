"""Scrape Simba Online Shopping's public ASP.NET product listings."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


CATALOG_URL = (
    "https://www.simbaonlineshopping.com/Products.aspx?main_cat_ID=1&"
    "main_cat_name=Food%20Products&sub_cat_name=Peanut%20Butter&subcat=60"
)


def _clean(values) -> str:
    return " ".join(" ".join(values).split())


def parse_products(response):
    """Yield complete positive-price products from ASP.NET repeater cards."""
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.img-thumbnail"):
        product_id = card.css('input[id*="hfItemID"]::attr(value)').get(default="").strip()
        name = _clean(card.css("div.proName ::text").getall())
        price_text = card.css('input[id*="hfUnitPrice"]::attr(value)').get(default="").strip()
        category = card.css('input[id*="hdCatName_rptr"]::attr(value)').get(default="").strip()
        subcategory = card.css('input[id*="hdfsub_cat_name_rptr"]::attr(value)').get(default="").strip()
        if not product_id or product_id in seen or not name:
            continue
        try:
            price = Decimal(price_text.replace(",", ""))
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": (subcategory or category or "consumer goods")[:500],
            "price": format(price, "f"),
            "currency": "XAF",
            "country": "Central African Republic",
            "sector": "consumer_goods",
            "available": True,
            "url": f"{response.url}#product-{product_id}",
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class CentralAfricanRepublicSimbaOnlineShoppingSpider(scrapy.Spider):
    name = "central_african_republic_simbaonlineshopping"
    allowed_domains = ["simbaonlineshopping.com", "www.simbaonlineshopping.com"]
    start_urls = [CATALOG_URL]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    def parse(self, response):
        yield from parse_products(response)
