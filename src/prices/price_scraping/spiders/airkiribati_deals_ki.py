"""Air Kiribati advertised domestic special fares."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_FARE_RE = re.compile(
    r"Fly To\s+(?P<destination>.+?)\s+AU\s*\$\s*(?P<price>[0-9]+)\s*/\s*person",
    re.I,
)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: object) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class AirKiribatiDealsKiSpider(scrapy.Spider):
    name = "airkiribati_deals_ki"
    allowed_domains = ["airkiribati.com.ki", "www.airkiribati.com.ki"]
    start_urls = ["https://airkiribati.com.ki/deals-promotions/"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        body_text = _clean(
            " ".join(
                response.xpath(
                    "//body//text()[not(ancestor::script) and not(ancestor::style)]"
                ).getall()
            )
        )

        for match in _FARE_RE.finditer(body_text):
            destination = _clean(match.group("destination")).title()
            price = match.group("price")
            product_id = f"airkiribati-special-fare-{_slug(destination)}"
            yield {
                "product_id": product_id,
                "product_name": f"Air Kiribati special fare - {destination}",
                "category": "Domestic air fare",
                "price": price,
                "currency": self.currency,
                "available": True,
                "unit": "person",
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
