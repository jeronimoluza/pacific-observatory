"""RwandaMart WooCommerce shop catalogue (RWF)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_START_URLS = [
    "https://rwandamart.rw/shop/",
    "https://rwandamart.rw/product-category/grocery-gourmet-food/",
    "https://rwandamart.rw/product-category/beverages/",
    "https://rwandamart.rw/product-category/breads-bakery/",
    "https://rwandamart.rw/product-category/biscuits-snacks/",
]
_PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)")


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _price(value: object) -> str | None:
    match = _PRICE_RE.search(_clean(value))
    if not match:
        return None
    number = match.group(1).replace(",", "")
    try:
        return f"{float(number):.2f}"
    except ValueError:
        return None


class RwandaMartRwSpider(scrapy.Spider):
    name = "rwanda_rwandamart_rw"
    allowed_domains = ["rwandamart.rw"]
    currency = "RWF"
    language = "en"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.25,
    }

    async def start(self):
        for url in _START_URLS:
            yield scrapy.Request(url, callback=self.parse_shop)

    def parse_shop(self, response):
        for card in response.css(".products > div.product"):
            link = card.css("h3.product-title a[href*='/product/']")
            href = link.attrib.get("href") if link else None
            name = _clean(link.css("::text").get() if link else None)
            price = _price(" ".join(card.css(".price .woocommerce-Price-amount ::text").getall()))
            classes = card.attrib.get("class", "")
            product_id = _product_id(classes)
            if not href or not name or not price or not product_id:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": _category(classes),
                "price": price,
                "currency": _clean(card.css(".price .woocommerce-Price-currencySymbol::text").get()) or self.currency,
                "available": "in-stock" in " ".join(card.css(".product-available::attr(class)").getall()),
                "store": _clean(card.css(".store-info a::text").get()) or None,
                "url": response.urljoin(href).split("?", 1)[0],
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        next_href = response.css("nav.woocommerce-pagination a.next::attr(href), a.next.page-numbers::attr(href)").get()
        if next_href:
            yield response.follow(next_href, self.parse_shop)


def _product_id(classes: str) -> str | None:
    for part in classes.split():
        if part.startswith("post-"):
            value = part.removeprefix("post-")
            if value.isdigit():
                return value
    return None


def _category(classes: str) -> str | None:
    for part in classes.split():
        if part.startswith("product_cat-"):
            return part.removeprefix("product_cat-")
    return None
