"""Docomo Pacific prepaid mobile plan and rate prices for Guam/CNMI."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _unit(price_text: str, fallback: str) -> str:
    if "/" in price_text:
        unit = price_text.split("/", 1)[1].strip()
        if unit:
            return f"per {unit.lower()}"
    return fallback


class DocomoPrepaidMpSpider(scrapy.Spider):
    name = "docomo_prepaid_mp"
    allowed_domains = ["docomopacific.com", "www.docomopacific.com"]
    start_urls = ["https://www.docomopacific.com/shop/mobile/prepaid/"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()

        for card in response.css(".docomo-lite-data-card"):
            title = _clean(
                " ".join(
                    card.css(".docomo-lite-data-card__rv-plan-name ::text").getall()
                )
            )
            price_text = _clean(
                " ".join(card.css(".docomo-lite-data-card__rv-price ::text").getall())
            )
            duration = _clean(
                " ".join(
                    card.css(".docomo-lite-data-card__rv-duration ::text").getall()
                )
            )
            price_match = _PRICE_RE.search(price_text)
            if not title or not price_match:
                continue
            features = " | ".join(
                _clean(" ".join(item.css("::text").getall()))
                for item in card.css(".docomo-lite-data-card__rv-item")
                if _clean(" ".join(item.css("::text").getall()))
            )
            product_id = _slug(f"plan-{title}-{duration}-{price_match.group(1)}")
            if product_id in seen:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": f"Docomo Pacific {title} prepaid plan",
                "category": "Mobile prepaid plan",
                "price": price_match.group(1),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": duration or "prepaid plan",
                "plan_features": features or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        for row in response.css(".docomo-rate-leader-list__row"):
            label = _clean(
                " ".join(row.css(".docomo-rate-leader-list__label ::text").getall())
            )
            price_text = _clean(
                " ".join(row.css(".docomo-rate-leader-list__value ::text").getall())
            )
            price_match = _PRICE_RE.search(price_text)
            if not label or not price_match:
                continue
            if "call" in label.lower() and "/sms" in price_text.lower():
                self.logger.warning(
                    "Skipping inconsistent Docomo rate row: %s -> %s",
                    label,
                    price_text,
                )
                continue
            product_id = _slug(f"rate-{label}-{price_text}")
            if product_id in seen:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": f"Docomo Pacific prepaid rate {label}",
                "category": "Mobile prepaid usage rate",
                "price": price_match.group(1),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": _unit(price_text, "prepaid usage"),
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
