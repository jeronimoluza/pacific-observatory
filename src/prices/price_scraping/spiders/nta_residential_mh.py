"""Marshall Islands NTA residential broadband tariff cards."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class NtaResidentialMhSpider(scrapy.Spider):
    name = "nta_residential_mh"
    allowed_domains = ["nta.mh", "www.nta.mh"]
    start_urls = ["https://www.nta.mh/residential/"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css(".elementor-price-table"):
            title = _clean(card.css(".elementor-price-table__heading ::text").get())
            price_text = _clean(
                " ".join(card.css(".elementor-price-table__price ::text").getall())
            )
            match = _PRICE_RE.search(price_text)
            if not title or not match:
                continue
            yield {
                "product_id": _slug(title),
                "product_name": title,
                "category": "Residential broadband plan",
                "price": match.group(0).replace(",", ""),
                "currency": "USD",
                "available": True,
                "unit": "per month",
                "url": f"{response.url}#{_slug(title)}",
                "language": "en",
                "scraped_at_utc": scraped_at,
            }
