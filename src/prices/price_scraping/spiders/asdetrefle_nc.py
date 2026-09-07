"""L'As de Trefle New Caledonia toy category parser."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _price(text: str | None) -> str | None:
    match = re.search(r"(\d[\d\s\u00a0\u202f]*)\s*XPF", text or "", re.I)
    if not match:
        return None
    return re.sub(r"\D", "", match.group(1))


class AsDeTrefleNcSpider(scrapy.Spider):
    name = "asdetrefle_nc"
    allowed_domains = ["www.asdetrefle.nc", "asdetrefle.nc"]
    start_urls = [
        "https://www.asdetrefle.nc/default/jouets/univers-1er-age/jouets-1er-age.html"
    ]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        for card in response.css("li.product-item"):
            product_id = card.css('[data-product-id]::attr(data-product-id)').get()
            name = _clean(card.css("a.product-item-link::text").get())
            price = (
                card.css("[data-price-amount]::attr(data-price-amount)").get()
                or _price(card.css(".price::text").get())
            )
            url = card.css("a.product-item-link::attr(href)").get()
            sku = _clean(card.css(".sku-info span::text").getall()[-1]) if card.css(".sku-info span::text").getall() else None
            if not (product_id and name and price):
                continue
            yield {
                "product_id": sku or product_id,
                "product_name": name[:500],
                "category": "jouets 1er age",
                "price": str(price),
                "currency": self.currency,
                "available": "En stock" in _clean(card.xpath("string(.)").get()),
                "url": url or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        next_url = response.css('a.next::attr(href), a[title="Suivant"]::attr(href)').get()
        if next_url:
            yield response.follow(next_url, callback=self.parse)
