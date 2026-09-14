"""Foodland Sierra Leone — WooCommerce catalogue and PDP price details.

The public ``/shop/`` page exposes product-category and paginated product
links.  Each PDP has a JSON-LD Product/Offer plus a visible description with
the important wholesale fields (``Unit Per CRT``, ``Unit Price Le``, ``Crt
Price Le``, and sometimes ``BarCode``).  The core price is the unit price;
the two explicit price-basis fields are retained in raw output so carton
prices are not lost.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import scrapy


_SHOP_URL = "https://foodland.sl/shop/"
_PRICE_RE = re.compile(r"(?:Unit|Crt)\\s+Price\\s+Le\\s*([0-9][0-9,]*(?:\\.[0-9]+)?)", re.I)
_UNIT_PRICE_RE = re.compile(r"Unit\\s+Price\\s+Le\\s*([0-9][0-9,]*(?:\\.[0-9]+)?)", re.I)
_CARTON_PRICE_RE = re.compile(r"Crt\\s+Price\\s+Le\\s*([0-9][0-9,]*(?:\\.[0-9]+)?)", re.I)
_PACK_RE = re.compile(r"Unit\\s+Per\\s+CRT\\s*([0-9]+)", re.I)
_BARCODE_RE = re.compile(r"BarCode\\s*([A-Za-z0-9._-]+)", re.I)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\\xa0", " ").split())


def _price(value: object) -> str | None:
    text = _clean(value).replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return f"{number:.2f}" if number > 0 else None


def _walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


class SierraLeoneFoodlandSlSpider(scrapy.Spider):
    name = "sierra_leone_foodland_sl"
    allowed_domains = ["foodland.sl"]
    currency = "SLL"
    language = "en"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.25,
    }

    async def start(self):
        yield scrapy.Request(_SHOP_URL, callback=self.parse_shop)

    def parse_shop(self, response):
        # Discover categories from the catalogue root.  This deliberately
        # excludes navigation links elsewhere in the page.
        for card in response.css("li.product-category a[href*='/product-category/']"):
            href = card.attrib.get("href")
            category = _clean(card.css("h2::text").get())
            if href:
                yield response.follow(href, self.parse_listing, cb_kwargs={"category": category})

        # Products shown directly on /shop/ can include uncategorised stock.
        yield from self._listing_requests(response, None)

    def parse_listing(self, response, category: str | None):
        yield from self._listing_requests(response, category)

    def _listing_requests(self, response, category: str | None):
        for card in response.css("li.product a.woocommerce-LoopProduct-link[href*='/product/']"):
            href = card.attrib.get("href")
            if href:
                yield response.follow(href, self.parse_product, cb_kwargs={"category": category})

        next_href = response.css("nav.woocommerce-pagination a.next::attr(href)").get()
        if next_href:
            yield response.follow(next_href, self.parse_listing, cb_kwargs={"category": category})

    def parse_product(self, response, category: str | None):
        product = self._jsonld_product(response)
        if not product:
            return
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if not isinstance(offers, dict):
            offers = {}
        specifications = offers.get("priceSpecification") or []
        if isinstance(specifications, dict):
            specifications = [specifications]
        offer_price = offers.get("price")
        if not offer_price and specifications:
            offer_price = specifications[0].get("price")

        description = _clean(product.get("description") or response.css("#tab-description").get())
        unit_price = self._match_price(_UNIT_PRICE_RE, description) or _price(offer_price)
        if unit_price is None:
            return
        carton_price = self._match_price(_CARTON_PRICE_RE, description)
        units_per_carton = self._match(_PACK_RE, description)
        barcode = self._match(_BARCODE_RE, description)
        sku = _clean(product.get("sku"))
        name = _clean(product.get("name") or response.css("h1.product_title::text").get())
        if not name:
            return
        category = category or " > ".join(_clean(value) for value in response.css(".product_meta .posted_in a::text").getall()) or None

        availability = _clean(offers.get("availability")).lower()
        product_id = barcode or sku or response.url.rstrip("/").rsplit("/", 1)[-1]
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": unit_price,
            "unit_price": unit_price,
            "carton_price": carton_price,
            "units_per_carton": units_per_carton,
            "barcode": barcode or None,
            "currency": offers.get("priceCurrency") or self.currency,
            "available": availability.endswith("instock"),
            "url": response.url.split("?", 1)[0],
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _match(pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    @classmethod
    def _match_price(cls, pattern: re.Pattern[str], text: str) -> str | None:
        value = cls._match(pattern, text)
        return _price(value) if value else None

    @staticmethod
    def _jsonld_product(response) -> dict | None:
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                payload = json.loads(script)
            except ValueError:
                continue
            for node in _walk(payload):
                node_type = node.get("@type")
                if node_type == "Product" or (isinstance(node_type, list) and "Product" in node_type):
                    return node
        return None
