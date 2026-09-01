"""Tuvalu Telecom mobile internet 4G plan prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_ALLOWANCE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?\s*(?:GB|MB)$", re.I)
_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class TuvaluTelecom4gSpider(scrapy.Spider):
    name = "tuvalu_telecom_4g"
    allowed_domains = ["tuvalutelecom.tv", "www.tuvalutelecom.tv"]
    start_urls = ["https://www.tuvalutelecom.tv/4g-plan"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        texts = [
            _clean(" ".join(node.css("::text").getall()))
            for node in response.css(".wixui-rich-text")
        ]
        texts = [item for item in texts if item]

        seen = set()
        for index, text in enumerate(texts[:-1]):
            if not _ALLOWANCE_RE.match(text):
                continue
            price_text = next(
                (
                    candidate
                    for candidate in texts[index + 1 : index + 4]
                    if _PRICE_RE.search(candidate)
                ),
                None,
            )
            price_match = _PRICE_RE.search(price_text or "")
            if not price_match:
                continue
            label = texts[index - 1] if index else ""
            if _ALLOWANCE_RE.match(label) or _PRICE_RE.search(label):
                label = ""
            validity = next(
                (
                    candidate
                    for candidate in texts[index + 1 : index + 4]
                    if "valid" in candidate.lower()
                ),
                "",
            )
            price = price_match.group(1)
            key = (label.lower(), text.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = _slug(f"4g-{label}-{text}-{price}")
            product_name = f"Tuvalu Telecom 4G mobile internet {text}"
            if label:
                product_name = f"Tuvalu Telecom {label} 4G mobile internet {text}"
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "category": "Mobile internet data plan",
                "price": price,
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": validity or "data plan",
                "data_allowance": text,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
