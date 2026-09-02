"""Timbu Kiribati data-plan price listing."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"\$?\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class TimbuKiribatiDataSpider(scrapy.Spider):
    name = "timbu_kiribati_data"
    allowed_domains = ["timbu.com", "www.timbu.com"]
    start_urls = [
        "https://timbu.com/kiribati/networks/amalgamated-telecom-holdings-kirbati/dataplan"
    ]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        for card in response.css(".c-plan"):
            plan_type = _clean(card.css(".c-plan-size::text").get())
            details = _clean(card.css(".c-plan-meta::text").get())
            price_text = _clean(card.css(".c-plan-price::text").get())
            price_match = _PRICE_RE.search(price_text)
            if not plan_type or not details or not price_match:
                continue

            product_name = f"ATH Kiribati {plan_type} data plan - {details}"
            price = price_match.group(1)
            product_id = _slug(f"{product_name}-{price}")
            if product_id in seen:
                continue
            seen.add(product_id)

            yield {
                "product_id": product_id,
                "product_name": product_name[:500],
                "category": "Mobile data tariff",
                "price": price,
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": plan_type,
                "plan_features": details,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
