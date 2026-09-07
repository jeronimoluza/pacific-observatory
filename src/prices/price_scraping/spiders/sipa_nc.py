"""SIPA New Caledonia furniture and appliances category-card parser."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _price(text: str | None) -> str | None:
    match = re.search(r"(\d[\d\s\u00a0\u202f]*)\s*F", text or "", re.I)
    if not match:
        return None
    return re.sub(r"\D", "", match.group(1))


class SipaNcSpider(scrapy.Spider):
    name = "sipa_nc"
    allowed_domains = ["www.sipa.nc", "sipa.nc"]
    start_urls = ["https://www.sipa.nc/sejour.html"]
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
        for card in response.css("ul.products-grid li.item"):
            url = card.css("h3.product-name a::attr(href)").get()
            name = _clean(card.css("h3.product-name a::text").get())
            prices = [
                _price(text)
                for text in card.css(".price-box .price::text").getall()
            ]
            prices = [p for p in prices if p]
            price = prices[-1] if prices else _price(card.xpath("string(.)").get())
            if not (name and price and url):
                continue
            product_id = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "sejour",
                "price": price,
                "currency": self.currency,
                "available": "Disponible" in _clean(card.xpath("string(.)").get()),
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        next_url = response.css('link[rel="next"]::attr(href), a.next::attr(href)').get()
        if next_url:
            yield response.follow(next_url, callback=self.parse)
