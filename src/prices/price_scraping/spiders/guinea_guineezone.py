"""Scrape current tangible-goods offers from GuineaZone."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


PRICE_RE = re.compile(r"([0-9][0-9 ]*)\s*GNF\b", re.IGNORECASE)
ID_RE = re.compile(r"^/([0-9a-f]{32})/")
NON_PRODUCT_RE = re.compile(
    r"\b(?:ads? boost|publicitaire|immobilier|terrain|parcelle|formation|coaching)\b|"
    r"\b(?:a|à) louer\b|\blocation (?:maison|appartement|bureau|magasin)\b",
    re.IGNORECASE,
)


def parse_cards(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.item-card"):
        url = card.css("a.item-card__link::attr(href)").get()
        id_match = ID_RE.match(url or "")
        name = " ".join(card.css("h3.item-card__title").xpath("string(.)").get(default="").split())
        price_text = " ".join(card.css("span.item-card__price-main").xpath("string(.)").get(default="").split())
        price_match = PRICE_RE.search(price_text)
        if not id_match or not name or not price_match or NON_PRODUCT_RE.search(name):
            continue
        product_id = id_match.group(1)
        if product_id in seen:
            continue
        try:
            price = Decimal(price_match.group(1).replace(" ", ""))
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": "marketplace",
            "price": format(price, "f"),
            "currency": "GNF",
            "country": "Guinea",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "fr",
            "scraped_at_utc": scraped_at,
        }


class GuineaGuineezoneSpider(scrapy.Spider):
    name = "guinea_guineezone"
    allowed_domains = ["guineezone.com"]
    start_urls = ["https://guineezone.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_cards(response)
