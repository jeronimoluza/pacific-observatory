"""Extract positive Shell Beans menu items from WooCommerce page markup."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


URL = "https://shellbeans.com/product/tuna-mayo-sandwich-signature/"


def clean(parts: list[str]) -> str:
    return " ".join(" ".join(parts).replace("\xa0", " ").split())


def amount(parts: list[str]) -> str | None:
    match = re.search(r"\d+(?:[.,]\d{1,2})?", clean(parts).replace(",", ""))
    if not match or float(match.group()) <= 0:
        return None
    return match.group()


class ShellBeansMvSpider(scrapy.Spider):
    name = "shellbeans_mv"
    allowed_domains = ["shellbeans.com"]
    custom_settings = {"DOWNLOAD_DELAY": 0.5, "CONCURRENT_REQUESTS_PER_DOMAIN": 1}

    async def start(self):
        yield scrapy.Request(URL, callback=self.parse)

    def parse(self, response):
        cards = response.css("div.products-entry")
        main = response.css("div.main-single-product")
        if main:
            cards = [main[0], *cards]
        seen: set[str] = set()
        for card in cards:
            name = clean(card.css("h1.product_title ::text, h3.product-title ::text").getall())
            currency = clean(card.css(".woocommerce-Price-currencySymbol ::text").getall())
            price = amount(card.css(".woocommerce-Price-amount ::text").getall())
            url = card.css("h1.product_title + .price-single + * a::attr(href), h3.product-title a::attr(href)").get()
            if not url and name == "TUNA MAYO SANDWICH":
                url = response.url
            if not name or currency != "MVR" or not price or not url:
                continue
            canonical_url = response.urljoin(url)
            if canonical_url in seen:
                continue
            seen.add(canonical_url)
            yield {
                "product_id": f"shellbeans:{canonical_url.rsplit('/', 2)[-2]}",
                "product_name": name,
                "price": price,
                "currency": currency,
                "channel": "restaurant_menu",
                "locality": "Malé, Maldives",
                "url": canonical_url,
                "language": "en",
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
