"""Vodafone Vanuatu WAO prepaid data plan prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"([0-9][0-9,]*)\s*vt\b", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class VodafoneVuWaoSpider(scrapy.Spider):
    name = "vodafone_vu_wao"
    allowed_domains = ["vodafone.com.vu", "www.vodafone.com.vu"]
    start_urls = ["https://vodafone.com.vu/pages/mobile-wao-data"]
    currency = "VUV"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for card in response.css(".plan_item"):
            title = _clean(" ".join(card.css("h4 ::text, h4::text").getall()))
            price_text = _clean(
                " ".join(card.css(".price ::text, .price::text").getall())
            )
            price_match = _PRICE_RE.search(price_text)
            if not title or not price_match:
                continue

            details = {}
            for row in card.css("p"):
                parts = [
                    _clean(part)
                    for part in row.css("label::text, span::text, ::text").getall()
                ]
                parts = [part for part in parts if part and part != "-"]
                if len(parts) >= 2:
                    label = parts[0].rstrip(":")
                    details[label] = " ".join(parts[1:])

            price = price_match.group(1).replace(",", "")
            data_allowance = details.get("Data")
            validity = details.get("Validity")
            key = (title.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = _slug(f"{title}-{price}")

            yield {
                "product_id": product_id,
                "product_name": title,
                "category": "Mobile prepaid data plan",
                "price": price,
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": validity or "prepaid plan",
                "data_allowance": data_allowance,
                "plan_features": " | ".join(f"{k}: {v}" for k, v in details.items())
                or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
