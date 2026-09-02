"""Vodafone French Polynesia mobile and prepaid offer tariffs."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_MOBILE_TITLES = {
    "Prestige",
    "Smile",
    "Vodacard 500",
    "Vodacard Internet",
    "Travel SIM",
    "Pack Mobiles",
}
_PRICE_RE = re.compile(r"([0-9][0-9\s]*)\s*F", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class VodafonePfMobileSpider(scrapy.Spider):
    name = "vodafone_pf_mobile"
    allowed_domains = ["vodafone.pf", "www.vodafone.pf"]
    start_urls = ["https://www.vodafone.pf/nos-offres/"]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css(".offer-card"):
            title = _clean(" ".join(card.css("h3::text, h3 *::text").getall()))
            if title not in _MOBILE_TITLES:
                continue
            text = _clean(" ".join(card.css("::text").getall()))
            price_scope = text[len(title) :].strip() if text.startswith(title) else text
            price_match = _PRICE_RE.search(price_scope)
            if not price_match:
                continue
            href = card.xpath(
                './/a[contains(normalize-space(.), "Composer") '
                'or contains(normalize-space(.), "Decouvrir") '
                'or contains(normalize-space(.), "Découvrir")]/@href'
            ).get()
            if not href:
                href = card.css("a[href]::attr(href)").get()
            product_id = _slug(title)
            yield {
                "product_id": product_id,
                "product_name": f"Vodafone Polynesie {title}"[:500],
                "category": "Mobile prepaid and plan tariff",
                "price": price_match.group(1).replace(" ", ""),
                "price_text": f"{price_match.group(1)}F",
                "currency": self.currency,
                "available": True,
                "unit": "plan",
                "features": text,
                "url": response.urljoin(href)
                if href
                else f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
