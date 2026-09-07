"""DPA Carmart Saipan used-car inventory."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"\*+\s*\$?\s*([0-9][0-9,]*(?:\.\d{1,2})?)\s*!*")
_MAKE_RE = re.compile(
    r"\b(?:Toyota|Honda|Nissan|Jeep|Mazda|Lexus|Ford|Chevrolet|Hyundai|Kia|Mitsubishi)\b",
    re.I,
)


def _clean(value: object) -> str:
    text = html.unescape(str(value or "")).replace("\xa0", " ").replace("\u200b", " ")
    return " ".join(text.split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:180]


class DpaCarmartMpSpider(scrapy.Spider):
    name = "dpa_carmart_mp"
    allowed_domains = ["dpacarmart.com", "www.dpacarmart.com"]
    start_urls = ["https://www.dpacarmart.com/inventory"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        blocks = [
            _clean(" ".join(node.css("::text").getall()))
            for node in response.css('[data-testid="richTextElement"]')
        ]
        blocks = [block for block in blocks if block]
        seen: set[tuple[str, str]] = set()

        for index, title in enumerate(blocks[:-1]):
            description = blocks[index + 1]
            if "$" not in description or _MAKE_RE.search(description) or not _MAKE_RE.search(title):
                continue
            price_segment = re.split(r"\bPRICE\b|\bFINANCING\b", description, maxsplit=1)[0]
            if re.search(r"\b(?:SOLD|PENDING)\b", price_segment, re.I):
                continue
            price_match = _PRICE_RE.search(price_segment)
            if not price_match:
                continue
            price = price_match.group(1).replace(",", "")
            if float(price) <= 0:
                continue
            key = (title.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = hashlib.sha1(f"{title}|{price}".encode("utf-8")).hexdigest()[:16]

            yield {
                "product_id": product_id,
                "product_name": title[:500],
                "category": "Used passenger vehicles",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#vehicle-{_slug(title)}-{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
