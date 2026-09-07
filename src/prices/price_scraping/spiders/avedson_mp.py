"""Avedson Marketplace Saipan electronics and household goods."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlparse

import scrapy

_PRICE_RE = re.compile(r"\$\s*(\d[\d,]*(?:\.\d{1,2})?)")


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:180]


class AvedsonMpSpider(scrapy.Spider):
    name = "avedson_mp"
    allowed_domains = ["avedson.com", "www.avedson.com"]
    start_urls = ["https://avedson.com/"]
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
        seen: set[str] = set()

        for card in response.css("div.product-card-modern"):
            name = _clean(card.css(".product-card-title-name::text").get())
            href = card.css("a.product-card-title-link::attr(href)").get()
            price_text = _clean(" ".join(card.css("h4.product-card-price::text").getall()))
            price_match = _PRICE_RE.search(price_text)
            if not name or not href or not price_match:
                continue
            price = price_match.group(1).replace(",", "")
            if float(price) <= 0:
                continue
            url = urljoin(response.url, href)
            key = f"{url}|{price}"
            if key in seen:
                continue
            seen.add(key)
            product_id = self._product_id(url, name, price)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Electronics and household durables",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _product_id(url: str, name: str, price: str) -> str:
        parsed = urlparse(url)
        variant = parse_qs(parsed.query).get("variant", [""])[0]
        if variant:
            return variant
        slug = parsed.path.rstrip("/").split("/")[-1] or _slug(name)
        return hashlib.sha1(f"{slug}|{price}".encode("utf-8")).hexdigest()[:16]
