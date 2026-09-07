"""Benson Guam Epicor storefront category pages."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"^\$\s*(\d[\d,]*(?:\.\d{1,2})?)$")
_SKIP = {
    "add to cart",
    "add to list",
    "benson guam ent.",
    "change",
    "continue shopping",
    "current language english change",
    "current store benson guam ent. change",
    "departments",
    "file not found",
    "image",
    "page",
    "view details",
    "welcome!",
}


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(text.replace("\xa0", " ").split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:180]


class BensonGuamSpider(scrapy.Spider):
    name = "benson_guam"
    allowed_domains = ["bensonguam.epicor-inet.com", "bensonguam.com", "www.bensonguam.com"]
    start_urls = [
        "https://bensonguam.epicor-inet.com/departments/portable-electric-generator-%7C50%7C127%7C001274.html",
    ]
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
        texts = [
            _clean(text)
            for text in response.xpath(
                "//body//text()[not(ancestor::script) and not(ancestor::style)]"
            ).getall()
        ]
        texts = [text for text in texts if text]
        seen: set[tuple[str, str]] = set()

        for index, text in enumerate(texts):
            price_match = _PRICE_RE.match(text)
            if not price_match:
                continue
            name = self._nearby_name(texts, index)
            if not name:
                continue
            price = price_match.group(1).replace(",", "")
            key = (name.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = hashlib.sha1(f"{name}|{price}".encode("utf-8")).hexdigest()[:16]
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Portable generators and hardware",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#product-{_slug(name)}-{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _nearby_name(texts: list[str], price_index: int) -> str | None:
        for candidate in reversed(texts[max(0, price_index - 5) : price_index]):
            candidate = _clean(candidate).strip(" -:;")
            lowered = candidate.lower()
            if not candidate or lowered in _SKIP:
                continue
            if lowered.startswith(("sku:", "image:", "page ", "current ")):
                continue
            if _PRICE_RE.match(candidate) or re.fullmatch(r"[\d\s./-]+", candidate):
                continue
            if len(candidate) > 90:
                continue
            return candidate
        return None
