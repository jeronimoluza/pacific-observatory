"""Marshall Islands NTA 4G LTE plan and voucher prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"\$\s*([0-9]+)(?:\s+([0-9]{2})\b|\.[0-9]{1,2})?")
_VOUCHER_RE = re.compile(r"\$([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _extract_price(text: str) -> str | None:
    match = _PRICE_RE.search(text)
    if not match:
        return None
    dollars = match.group(1)
    cents = match.group(2)
    return f"{dollars}.{cents}" if cents else dollars


class Nta4gMhSpider(scrapy.Spider):
    name = "nta_4g_mh"
    allowed_domains = ["nta.mh", "www.nta.mh"]
    start_urls = ["https://www.nta.mh/4g-lte-plans/"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for card in response.css(".elementor-price-table"):
            title = _clean(card.css(".elementor-price-table__heading ::text").get())
            price_text = _clean(
                " ".join(card.css(".elementor-price-table__price ::text").getall())
            )
            price = _extract_price(price_text)
            if not title or not price:
                continue
            features = [
                _clean(" ".join(item.css("::text").getall()))
                for item in card.css(".elementor-price-table__features-list li")
            ]
            features = [item for item in features if item]
            product_id = _slug(title)
            key = ("plan", title.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            yield {
                "product_id": product_id,
                "product_name": title,
                "category": "4G LTE monthly plan",
                "price": price,
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": "per month",
                "plan_features": " | ".join(features) or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        page_text = _clean(" ".join(response.css("p ::text, p::text").getall()))
        voucher_intro = re.search(
            r"vouchers come in the face values of ([^.]+)", page_text, re.I
        )
        if not voucher_intro:
            return
        for amount in _VOUCHER_RE.findall(voucher_intro.group(1)):
            product_id = _slug(f"lte-voucher-{amount}")
            key = ("voucher", amount)
            if key in seen:
                continue
            seen.add(key)
            yield {
                "product_id": product_id,
                "product_name": f"NTA LTE voucher ${amount}",
                "category": "4G LTE voucher",
                "price": amount,
                "currency": self.currency,
                "available": True,
                "unit": "voucher",
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
