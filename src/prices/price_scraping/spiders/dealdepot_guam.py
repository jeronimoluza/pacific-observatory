"""Deal Depot Guam Wix storefront product cards."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_PRICE_RE = re.compile(r"\$\s*(\d[\d,]*(?:\.\d{1,2})?)")


def _clean(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).replace("\xa0", " ").split())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:180]


class DealDepotGuamSpider(scrapy.Spider):
    name = "dealdepot_guam"
    allowed_domains = ["dealdepotguam.com", "www.dealdepotguam.com"]
    start_urls = ["https://www.dealdepotguam.com/category/all-products"]
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
        seen: set[tuple[str, str]] = set()

        for card in response.css('[data-hook="product-item-root"]'):
            name = _clean(card.css('[data-hook="product-item-name"]::text').get()).strip('"')
            price_text = _clean(
                card.css('[data-hook="product-item-price-to-pay"]::attr(data-wix-price)').get()
                or card.css('[data-hook="product-item-price-to-pay"]::text').get()
            )
            href = card.css('a[data-hook="product-item-container"]::attr(href)').get()
            slug = _clean(card.attrib.get("data-slug"))
            text = _clean(" ".join(card.css("::text").getall())).lower()
            price_match = _PRICE_RE.search(price_text)
            if not name or not price_match:
                continue
            price = price_match.group(1).replace(",", "")
            if float(price) <= 0:
                continue
            key = (slug or name.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            product_id = slug or hashlib.sha1(f"{name}|{price}".encode("utf-8")).hexdigest()[:16]
            url = urljoin(response.url, href or f"#product-{_slug(name)}")

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Furniture, home goods, apparel and small appliances",
                "price": price,
                "currency": self.currency,
                "available": "out of stock" not in text,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
