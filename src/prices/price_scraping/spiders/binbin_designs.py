"""Binbin Designs' server-rendered Gambian product catalogue."""
from __future__ import annotations

from datetime import datetime, timezone

import scrapy


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


class BinbinDesignsSpider(scrapy.Spider):
    name = "binbin_designs"
    allowed_domains = ["binbindesigns.com"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request("https://binbindesigns.com/")

    def parse(self, response):
        seen = set()
        for card in response.css("li.product"):
            href = card.css('a[href*="/product/"]::attr(href)').get()
            name = clean(card.css(".woocommerce-loop-product__title a::text").get())
            if name.lower().startswith("sample item"):
                continue
            price = clean(" ".join(card.css(".woocommerce-Price-amount::text").getall()))
            symbol = clean(card.css(".woocommerce-Price-currencySymbol::text").get())
            if not (href and name and price and symbol == "D"):
                continue
            value = price.replace(",", "")
            try:
                if float(value) <= 0:
                    continue
            except ValueError:
                continue
            url = response.urljoin(href).split("#", 1)[0]
            product_id = url.rstrip("/").rsplit("/", 1)[-1]
            if product_id in seen:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": value,
                "currency": "GMD",
                "country": "Gambia",
                "sector": "consumer_goods",
                "url": url,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
