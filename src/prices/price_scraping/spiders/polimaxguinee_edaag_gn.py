"""POLIMAX Guinea's server-rendered EDAAG catalogue (GNF)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_CATALOGUE_URL = "https://polimaxguinee.com/catalogue"
_NUMBER_RE = re.compile(r"([0-9][0-9\s,.]*)")
_CART_RE = re.compile(r"addToCart\(\s*['\"]?([^,'\" )]+)['\"]?\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]?([0-9.,]+)", re.I)


def _clean(value: object) -> str:
    if isinstance(value, (list, tuple)):
        value = " ".join(map(str, value))
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _price(value: object) -> str | None:
    match = _NUMBER_RE.search(_clean(value))
    if not match:
        return None
    raw = match.group(1).replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        return None
    return f"{amount:.2f}" if amount > 0 else None


class PolimaxguineeEdaagGnSpider(scrapy.Spider):
    name = "polimaxguinee_edaag_gn"
    allowed_domains = ["polimaxguinee.com"]
    currency = "GNF"
    language = "fr"
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.25}

    async def start(self):
        yield scrapy.Request(_CATALOGUE_URL, callback=self.parse_catalogue)

    def parse_catalogue(self, response):
        # Product cards are the authoritative scope: do not parse header/cart totals.
        for card in response.css(".product-card"):
            name = _clean(card.css(".product-name ::text, .product-name::text").getall())
            price = _price(card.css(".product-price ::text, .product-price::text").getall())
            if not name or not price:
                continue
            onclick = " ".join(card.css("[onclick*='addToCart']::attr(onclick)").getall())
            cart = _CART_RE.search(onclick)
            product_id = card.attrib.get("data-id") or (cart.group(1) if cart else None) or name
            category = _clean(card.attrib.get("data-category")) or None
            text = _clean(card.css("::text").getall())
            pack = _clean(card.css(".product-packaging ::text, .packaging ::text, .pcs-carton ::text").getall()) or None
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "store": "Magasin Central Madina",
                "packaging": pack,
                "available": "rupture" not in text.lower(),
                "url": f"{response.url}#product-{product_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
