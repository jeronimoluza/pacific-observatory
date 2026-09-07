"""E'lien Tahiti marketplace food and beverage category."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_START_URL = "https://www.elien.pf/marketplace/articlebycat/4/"
_PRICE_RE = re.compile(
    r"(?P<amount>\d+(?:[\s\u00a0\u202f]\d{3})*)\s*XPF\s*/\s*(?P<unit>[\w-]+)",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return " ".join(text.split())


class ElienAlimentationPfSpider(scrapy.Spider):
    name = "elien_alimentation_pf"
    allowed_domains = ["elien.pf", "www.elien.pf"]
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
        yield scrapy.Request(_START_URL, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css('div[id^="card-"]'):
            product_id = card.attrib.get("id", "").replace("card-", "")
            name = _clean(card.css(".card-title a::text").get())
            url = card.css(".card-title a::attr(href), a::attr(href)").get()
            price_text = _clean(card.xpath("string(.)").get())
            match = _PRICE_RE.search(price_text)
            if not product_id or not name or not match:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Alimentation et Boisson",
                "price": match.group("amount").replace(" ", ""),
                "price_text": match.group(0),
                "currency": self.currency,
                "available": True,
                "unit": match.group("unit"),
                "url": urljoin(response.url, url) if url else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
