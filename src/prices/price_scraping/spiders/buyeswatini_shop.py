"""Buy Eswatini's server-rendered product listing."""
from __future__ import annotations

from datetime import datetime, timezone

import scrapy


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


class BuyeswatiniShopSpider(scrapy.Spider):
    name = "buyeswatini_shop"
    allowed_domains = ["www.buyeswatini.shop"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request("https://www.buyeswatini.shop/291/Product/All")

    def parse(self, response):
        seen = set()
        for card in response.css("li"):
            href = card.css('a[href*="/Product/Detail/"]::attr(href)').get()
            name = clean(card.css(".products_title a::text").get())
            price = clean(" ".join(card.css(".products_guide::text").getall()))
            currency = clean(card.css(".products_guide span:last-child::text").get())
            if not (href and name and price and currency == "SZL"):
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
                "currency": "SZL",
                "country": "Eswatini",
                "sector": "consumer_goods",
                "url": url,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
