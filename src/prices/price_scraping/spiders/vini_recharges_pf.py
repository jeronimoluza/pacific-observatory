"""Vini French Polynesia prepaid mobile recharge tariffs."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_TITLE_PRICE_RE = re.compile(r"Recharge\s+([0-9][0-9\s]*)\s*F", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class ViniRechargesPfSpider(scrapy.Spider):
    name = "vini_recharges_pf"
    allowed_domains = ["vini.pf", "www.vini.pf"]
    start_urls = ["https://www.vini.pf/mobile/offres-prepayees/recharger"]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css(".node--type--encart"):
            title = _clean(card.css("h3::text").get())
            match = _TITLE_PRICE_RE.search(title)
            if not match:
                continue
            features = _clean(" ".join(card.css(".text-secondary-one ::text").getall()))
            price = match.group(1).replace(" ", "")
            product_id = _slug(title)
            yield {
                "product_id": product_id,
                "product_name": f"Vini {title}"[:500],
                "category": "Mobile prepaid recharge tariff",
                "price": price,
                "price_text": f"{match.group(1)} F",
                "currency": self.currency,
                "available": True,
                "unit": "recharge",
                "features": features or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
