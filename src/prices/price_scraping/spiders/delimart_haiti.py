"""Collect visually verified Delimart Haiti promotion-card prices."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy


PROMOTIONS_URL = "https://delimarthaiti.com/promotions"
_CAMPAIGN_MONTH = "2026-08"
_ASSET_RE = re.compile(
    rf"^/assets/images/prix-ate-plat/{_CAMPAIGN_MONTH}/"
    r"(pri-at-plat-[0-9a-f]+)\.png$"
)

# Manual transcription from the saved first-party cards. The old price is
# retained separately and is never substituted for the red-tag current price.
_VERIFIED_OFFERS = {
    "pri-at-plat-6a73334f185fc": {
        "product_name": "Brunswick Tuna Flaked with Sweet Corn",
        "unit": "142 g",
        "category": "food:tinned fish",
        "price": "250",
        "previous_price": "295",
    },
    "pri-at-plat-6a73334f18a2e": {
        "product_name": "Brunswick Tuna Flaked in Oil",
        "unit": "142 g",
        "category": "food:tinned fish",
        "price": "165",
        "previous_price": "185",
    },
    "pri-at-plat-6a73334f18dd1": {
        "product_name": "Abest Juice, assorted flavors",
        "unit": "330 ml",
        "category": "beverages:juice",
        "price": "95",
        "previous_price": "120",
    },
    "pri-at-plat-6a73334f190f0": {
        "product_name": "Black Bruin Multi Vitamine Energy Drink",
        "unit": "250 ml",
        "category": "beverages:energy drink",
        "price": "190",
        "previous_price": "210",
    },
    "pri-at-plat-6a73334f1948a": {
        "product_name": "Don Luciano Sparkling Wine, assorted varieties",
        "unit": "750 ml",
        "category": "beverages:alcoholic",
        "price": "850",
        "previous_price": "945",
    },
    "pri-at-plat-6a73334f1985a": {
        "product_name": "Fair & White Gel Creme Eclaircis",
        "unit": "30 ml",
        "category": "personal care:skin care",
        "price": "950",
        "previous_price": "1075",
    },
}


def parse_cards(response, scraped_at=None):
    """Yield only cards whose immutable asset IDs were visually verified."""
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    seen = set()
    for raw_url in response.css("figure.promo-card img::attr(src)").getall():
        image_url = response.urljoin(raw_url)
        match = _ASSET_RE.match(urlparse(image_url).path)
        if not match:
            continue
        product_id = match.group(1)
        offer = _VERIFIED_OFFERS.get(product_id)
        if offer is None or product_id in seen:
            continue
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": offer["product_name"],
            "unit": offer["unit"],
            "category": offer["category"],
            "price": offer["price"],
            "previous_price": offer["previous_price"],
            "currency": "HTG",
            "country": "Haiti",
            "location": "Port-au-Prince",
            "sector": "consumer_goods",
            "available": True,
            "url": image_url,
            "language": "fr-HT",
            "observation_date": f"{_CAMPAIGN_MONTH}-01",
            "period_kind": "month",
            "scraped_at_utc": scraped_at,
        }


class DelimartHaitiSpider(scrapy.Spider):
    name = "delimart_haiti"
    allowed_domains = ["delimarthaiti.com"]
    start_urls = [PROMOTIONS_URL]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse(self, response):
        yield from parse_cards(response)
