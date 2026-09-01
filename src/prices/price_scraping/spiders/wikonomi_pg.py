"""Wikonomi Papua New Guinea community product price directory."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"PGK\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class WikonomiPgSpider(scrapy.Spider):
    name = "wikonomi_pg"
    allowed_domains = ["wikonomi.com", "www.wikonomi.com"]
    start_urls = ["https://www.wikonomi.com/products/?page=1&q=&sort=popular"]
    currency = "PGK"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css('a[href^="/product/"]'):
            name = _clean(card.css("h2::text").get())
            href = card.attrib.get("href")
            if not name or not href:
                continue

            price_text = self._field_after_label(card, "Lowest")
            price_match = _PRICE_RE.search(price_text)
            if not price_match:
                continue

            latest_store = self._field_after_label(card, "Latest")
            report_count = self._stat_before_label(card, "reports")
            store_count = self._stat_before_label(card, "stores")
            product_id = href.rstrip("/").rsplit("/", 1)[-1] or _slug(name)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Community product price report",
                "price": price_match.group(1).replace(",", ""),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "vendor": latest_store or None,
                "n_observations": report_count or None,
                "store_count": store_count or None,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        next_href = response.xpath(
            '//a[normalize-space(.)="Next" and contains(@href, "page=")]/@href'
        ).get()
        if next_href:
            yield response.follow(next_href, callback=self.parse)

    @staticmethod
    def _field_after_label(card, label: str) -> str:
        return _clean(
            card.xpath(
                f'.//*[normalize-space()="{label}"]/following-sibling::*[1]/text()'
            ).get()
        )

    @staticmethod
    def _stat_before_label(card, label: str) -> str:
        return _clean(
            card.xpath(
                f'.//*[normalize-space()="{label}"]/preceding-sibling::*[1]/text()'
            ).get()
        )
