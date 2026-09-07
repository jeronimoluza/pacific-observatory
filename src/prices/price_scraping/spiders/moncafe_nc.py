"""Mon Cafe / Cafe Melanesien New Caledonia beverage catalog."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import scrapy

_START_URLS = [
    "https://www.moncafe.nc/10-cafes",
    "https://www.moncafe.nc/11-thes-et-tisanes",
]
_PRICE_RE = re.compile(r"\d[\d\s\u00a0\u202f.,]*")


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return " ".join(text.split())


class MonCafeNcSpider(scrapy.Spider):
    name = "moncafe_nc"
    allowed_domains = ["moncafe.nc", "www.moncafe.nc"]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for url in _START_URLS:
            yield scrapy.Request(url, callback=self.parse_category)

    def parse_category(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("article.product-miniature"):
            product_id = _clean(card.attrib.get("data-id-product"))
            name = _clean(
                card.css(
                    ".product-title a::text, .h3.product-title a::text, "
                    ".h4.product-title a::text, [itemprop='name']::text"
                ).get()
            )
            url = card.css(
                ".product-title a::attr(href), .thumbnail-container a::attr(href), "
                "a.thumbnail::attr(href)"
            ).get()
            price = self._price(card.xpath('string(.//*[contains(@class, "price")])').get())
            if not product_id or not name or price is None:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": self._category(response.url),
                "price": price,
                "currency": self.currency,
                "available": "rupture" not in _clean(card.xpath("string(.)").get()).lower(),
                "url": urljoin(response.url, url) if url else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _price(raw: object) -> str | None:
        match = _PRICE_RE.search(_clean(raw))
        if not match:
            return None
        value = match.group(0).replace(" ", "").replace(",", ".")
        try:
            parsed = float(value)
        except ValueError:
            return None
        if parsed <= 0:
            return None
        return str(int(parsed)) if parsed.is_integer() else f"{parsed:.2f}"

    @staticmethod
    def _category(url: str) -> str | None:
        path = urlsplit(url).path.strip("/")
        if "-" not in path:
            return path or None
        return path.split("-", 1)[1].replace("-", " ")
