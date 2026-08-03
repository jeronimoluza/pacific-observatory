"""
Spider for Capelle & Partner Online Delivery (Nauru) — cponlinedelivery.com

Wix-hosted grocery delivery catalogue. Every PDP carries a Schema.org Product
JSON-LD block with name, SKU, price, and priceCurrency (AUD); extracted without
CSS selectors. Category is derived from the referring category-page URL slug.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

CATEGORY_URLS = [
    "https://www.cponlinedelivery.com/cleaning-toiletries",
    "https://www.cponlinedelivery.com/drinks-and-chilled-goods",
    "https://www.cponlinedelivery.com/dry-goods",
    "https://www.cponlinedelivery.com/frozen-meats-fish",
    "https://www.cponlinedelivery.com/fruits-and-vegetables",
    "https://www.cponlinedelivery.com/health-wellbeing",
    "https://www.cponlinedelivery.com/pet",
    "https://www.cponlinedelivery.com/variety-items",
]


class CapelleNrSpider(scrapy.Spider):
    name = "capelle_nr"
    allowed_domains = ["www.cponlinedelivery.com", "cponlinedelivery.com"]
    currency = "AUD"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 1,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls: set[str] = set()

    async def start(self):
        for url in CATEGORY_URLS:
            slug = url.rsplit("/", 1)[-1]
            category = slug.replace("-", " ").title()
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                cb_kwargs={"category": category},
            )

    def parse_category(self, response, category):
        product_links = response.css(
            'a[data-hook="product-item-container"]::attr(href)'
        ).getall()
        logger.info(
            f"capelle_nr: category={category!r} found {len(product_links)} links"
        )
        for href in product_links:
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                cb_kwargs={"category": category},
            )

    def parse_product(self, response, category):
        product = self._extract_json_ld(response)
        if not product:
            logger.warning(f"No Product JSON-LD at {response.url}")
            return
        offer = product.get("Offers") or product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get("price")
        currency = offer.get("priceCurrency") or self.currency
        name = product.get("name")
        if not (price and name):
            logger.warning(f"Missing price or name at {response.url}")
            return
        yield {
            "product_id": product.get("sku"),
            "product_name": str(name).strip()[:500],
            "price": str(price),
            "currency": currency,
            "category": category,
            "url": response.url,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"capelle_nr: scraped {name!r} @ {currency} {price}")

    @staticmethod
    def _extract_json_ld(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and d.get("@type") == "Product":
                return d
        return None
