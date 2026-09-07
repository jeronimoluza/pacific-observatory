"""Palm Bay Bistro Palau beverage menu."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import scrapy
from w3lib.html import remove_tags

_PRICE_RE = re.compile(
    r"(?P<label>[A-Za-z][A-Za-z0-9 '&/.-]{0,60})?\s*\$(?P<price>\d+(?:\.\d+)?)"
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -:;,.()")


class PalmBayBistroPwSpider(scrapy.Spider):
    name = "palmbay_bistro_pw"
    allowed_domains = ["palmbaybistro.com", "www.palmbaybistro.com"]
    start_urls = ["https://www.palmbaybistro.com/drink"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        current_section = "Palm Bay Bistro drinks"
        current_label = None
        scraped_at = datetime.now(timezone.utc).isoformat()

        for node in response.css("h1, h2, p"):
            tag = node.root.tag.lower()
            text = _clean(remove_tags(" ".join(node.getall())))
            if not text:
                continue
            if tag in {"h1", "h2"}:
                current_section = text
                current_label = None
                continue

            matches = list(_PRICE_RE.finditer(text))
            if not matches:
                if len(text) <= 140 and not text.lower().startswith(("contact", "for reservations")):
                    current_label = text
                continue

            for idx, match in enumerate(matches):
                price = match.group("price")
                label = _clean(match.group("label") or "")
                if label and text.count("$") == 1:
                    name = label
                elif label:
                    name = f"{current_label or current_section} {label}"
                else:
                    name = current_label or current_section
                if not name:
                    continue
                row_key = f"{current_section}|{name}|{idx}|{price}"
                product_id = hashlib.md5(row_key.encode("utf-8")).hexdigest()
                yield {
                    "product_id": product_id,
                    "product_name": f"Palm Bay Bistro {name}"[:500],
                    "category": current_section,
                    "price": price,
                    "currency": self.currency,
                    "available": True,
                    "url": f"{response.url}#item-{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
