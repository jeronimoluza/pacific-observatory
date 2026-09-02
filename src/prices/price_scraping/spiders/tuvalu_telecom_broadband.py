"""Tuvalu Telecom broadband and Kasefika internet plan prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_ALLOWANCE_RE = re.compile(r"^(?:unlimited|[0-9]+(?:\.[0-9]+)?\s*GB)$", re.I)
_PLAN_RE = re.compile(r"^(?:Ocean\s*[0-9]+|TUV[0-9]+|Residential Plan)$", re.I)
_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class TuvaluTelecomBroadbandSpider(scrapy.Spider):
    name = "tuvalu_telecom_broadband"
    allowed_domains = ["tuvalutelecom.tv", "www.tuvalutelecom.tv"]
    start_urls = [
        "https://www.tuvalutelecom.tv/broadband-plans",
        "https://www.tuvalutelecom.tv/kasefika-satellite-internet",
    ]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = (
            "Satellite internet plan"
            if "kasefika" in response.url
            else "Broadband internet plan"
        )
        texts = [
            _clean(" ".join(node.css("::text").getall()))
            for node in response.css(".wixui-rich-text")
        ]
        texts = [text for text in texts if text]
        seen = set()

        for index, label in enumerate(texts):
            if not _PLAN_RE.match(label):
                continue
            window = []
            for text in texts[index + 1 :]:
                if _PLAN_RE.match(text) or text.lower().startswith(
                    ("faqs", "vision", "privacy policy", "business hours", "contact")
                ):
                    break
                window.append(text)
            price_text = next((text for text in window if _PRICE_RE.search(text)), "")
            price_match = _PRICE_RE.search(price_text)
            if not price_match:
                continue
            allowance = next((text for text in window if _ALLOWANCE_RE.match(text)), "")
            validity = next((text for text in window if "month" in text.lower()), "")
            plan_features = " | ".join(
                text for text in window if text not in {price_text, allowance, validity}
            )
            product_id = _slug(f"{category}-{label}-{price_match.group(1)}")
            if product_id in seen:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": f"Tuvalu Telecom {label} {category.lower()}"[:500],
                "category": category,
                "price": price_match.group(1),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": validity or "internet plan",
                "data_allowance": allowance or None,
                "plan_features": plan_features or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
