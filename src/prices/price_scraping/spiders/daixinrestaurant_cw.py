"""
Daixin Restaurant (Willemstad, Curacao) -- https://www.daixinrestaurant.com/nl/menu.
Asian / Chinese / Caribbean take-away restaurant on the Oracle Food Booking
platform. The menu page carries a schema.org Restaurant JSON-LD block whose
"menu" -> hasMenuSection[] -> hasMenuItem[] lists every dish with an Offer
price in ANG (62 items on 2026-10-12). Server-rendered, one request.
"""

import json
import re

import scrapy

_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_URL = "https://www.daixinrestaurant.com/nl/menu"


class DaixinrestaurantCwSpider(scrapy.Spider):
    name = "daixinrestaurant_cw"
    allowed_domains = ["daixinrestaurant.com"]
    currency = "ANG"
    language = "nl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse_menu)

    def parse_menu(self, response):
        for block in _LD_RE.findall(response.text):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if not isinstance(data, dict) or data.get("@type") != "Restaurant":
                continue
            menu = data.get("menu") or {}
            for section in menu.get("hasMenuSection") or []:
                sec_name = (section.get("name") or "").strip() or None
                for item in section.get("hasMenuItem") or []:
                    name = (item.get("name") or "").strip()
                    offer = item.get("offers") or {}
                    try:
                        price = float(offer.get("price"))
                    except (TypeError, ValueError):
                        continue
                    if not name or price <= 0:
                        continue
                    slug = re.sub(r"[^a-z0-9]+", "-", f"{sec_name}-{name}".lower()).strip("-")
                    yield {
                        "product_id": slug,
                        "product_name": name[:500],
                        "category": sec_name,
                        "price": str(price),
                        "currency": offer.get("priceCurrency") or self.currency,
                        "available": True,
                        "url": f"{_URL}#{slug}",
                        "language": self.language,
                    }
