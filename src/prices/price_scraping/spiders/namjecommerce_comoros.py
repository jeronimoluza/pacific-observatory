"""Namje Commerce homepage catalogue for Comoros consumer-product prices."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"(?:^|\s)([0-9][0-9\s.,]*)\s*KMF\b", re.I)


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


class NamjecommerceComorosSpider(scrapy.Spider):
    name = "namjecommerce_comoros"
    allowed_domains = ["namjecommerce.com"]
    start_urls = ["https://namjecommerce.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    def parse(self, response):
        # The current price is in h4 span; h4 sup is a crossed/previous value
        # and is often zero, so it must not be treated as the sale price.
        seen = set()
        for card in response.css(".products__container > .product"):
            name = clean(card.css("h5 a::text").get())
            raw_price = clean(card.css("h4 span::text").get())
            match = PRICE_RE.search(raw_price)
            href = card.css("h5 a::attr(href)").get()
            if not (name and match and href):
                continue
            url = response.urljoin(href).split("#", 1)[0]
            product_id = card.css('input[name="productId"]::attr(value)').get()
            product_id = product_id or url.rstrip("/").rsplit("/", 1)[-1] or name.lower()
            if product_id in seen:
                continue
            seen.add(product_id)
            value = match.group(1).replace(" ", "").replace(",", "")
            if float(value) <= 0:
                continue
            yield {
                "product_id": product_id[:250],
                "product_name": name[:500],
                "price": value,
                "currency": "KMF",
                "country": "Comoros",
                "sector": "consumer_goods",
                "url": url,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
