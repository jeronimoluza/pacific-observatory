"""Bluesky American Samoa prepaid mobile plan prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"\$?\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class BlueskyPrepaidAsSpider(scrapy.Spider):
    name = "bluesky_prepaid_as"
    allowed_domains = ["bluesky.as"]
    start_urls = ["https://www.bluesky.as/personal/prepaid/plans/"]
    currency = "USD"
    language = "en"

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for card in response.css(".prepaidplan-listing-box-item .card"):
            title = self._text(
                card.css(".card-header .title *::text, .card-header .title::text")
            )
            title = re.sub(r"\bNew\b", "", title, flags=re.I).strip()
            price_text = self._text(card.css(".card-footer .price::text"))
            price_match = _PRICE_RE.search(price_text)
            if not title or not price_match:
                continue

            main_tag = self._text(card.css(".main-tag *::text, .main-tag::text"))
            feature = self._text(card.css(".main-feature *::text, .main-feature::text"))
            validity = self._text(
                card.css(".main-validity *::text, .main-validity::text")
            )
            price = price_match.group(1)
            key = (title.lower(), price, main_tag.lower(), validity.lower())
            if key in seen:
                continue
            seen.add(key)

            slug = _SLUG_RE.sub("-", title.lower()).strip("-")
            yield {
                "product_id": slug or f"plan-{len(seen)}",
                "product_name": title,
                "category": "Mobile prepaid plans",
                "price": price,
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{slug}",
                "language": self.language,
                "data_allowance": main_tag or None,
                "plan_features": feature or None,
                "validity": validity or None,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _text(selector_list) -> str:
        return re.sub(r"\s+", " ", " ".join(selector_list.getall())).strip()
