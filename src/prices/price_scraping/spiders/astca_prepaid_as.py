"""ASTCA American Samoa prepaid mobile bundle prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class AstcaPrepaidAsSpider(scrapy.Spider):
    name = "astca_prepaid_as"
    allowed_domains = ["astca.as", "www.astca.as"]
    start_urls = ["https://www.astca.as/prepaid-mobile-data-plans/"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for index, card in enumerate(response.css(".dataBundle"), 1):
            title = _clean(" ".join(card.css(".title ::text, .title::text").getall()))
            validity = _clean(" ".join(card.css(".row2 ::text, .row2::text").getall()))
            price_text = _clean(
                " ".join(card.css(".row3 ::text, .row3::text").getall())
            )
            price_match = _PRICE_RE.search(price_text)
            if not title or not price_match:
                continue

            detail_parts = [
                _clean(" ".join(cell.css("::text").getall())) for cell in card.css("td")
            ]
            detail = " | ".join(part for part in detail_parts if part and part != title)
            product_name = f"ASTCA prepaid data {title}"
            if validity:
                product_name = f"{product_name} ({validity})"

            key = (
                title.lower(),
                validity.lower(),
                price_match.group(1),
                price_text.lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            product_id = _slug(f"{index}-{title}-{validity}-{price_match.group(1)}")

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "category": "Mobile prepaid data bundle",
                "price": price_match.group(1),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": validity or "prepaid bundle",
                "plan_features": detail or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
