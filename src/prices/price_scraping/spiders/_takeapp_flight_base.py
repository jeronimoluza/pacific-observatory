"""Shared parser for take.app storefronts with Next.js RSC product payloads."""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterable

import scrapy

logger = logging.getLogger(__name__)

_FLIGHT_CHUNK_RE = re.compile(
    r"self\.__next_f\.push\(\[\d+,(\"(?:\\.|[^\"\\])*\")\]\)", re.S
)
_PRODUCT_RE = re.compile(
    r'\{"id":"(?P<id>[^"\\]+)",'
    r'"name":"(?P<name>(?:\\.|[^"\\])*)",'
    r'"description":(?P<description>null|"(?:\\.|[^"\\])*").*?'
    r'"type":"PHYSICAL".*?'
    r'"price":(?P<price>\d+).*?'
    r'"soldout":(?P<soldout>true|false)',
    re.S,
)
_CURRENCY_RE = re.compile(r'"currency":"([A-Z]{3})"')
_COUNTRY_RE = re.compile(r'"countryCode":"([A-Z]{2})"')


class TakeAppFlightSpider(scrapy.Spider):
    """Base spider for take.app stores whose cards are in flight chunks only."""

    name = None
    allowed_domains = ["take.app"]
    currency: str = ""
    language: str = "en"
    STORE_ALIAS: str = ""
    COUNTRY_CODE: str | None = None

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

    async def start(self):
        yield scrapy.Request(
            f"https://take.app/{self.STORE_ALIAS}", callback=self.parse
        )

    def parse(self, response):
        decoded = "\n".join(self._flight_chunks(response.text))
        if not decoded:
            logger.warning("%s: no decoded take.app flight chunks", self.name)
            return

        currencies = set(_CURRENCY_RE.findall(decoded))
        countries = set(_COUNTRY_RE.findall(decoded))
        if self.currency and currencies and self.currency not in currencies:
            logger.warning(
                "%s: expected currency %s but page advertised %s",
                self.name,
                self.currency,
                sorted(currencies),
            )
        if self.COUNTRY_CODE and countries and self.COUNTRY_CODE not in countries:
            logger.warning(
                "%s: expected country %s but page advertised %s",
                self.name,
                self.COUNTRY_CODE,
                sorted(countries),
            )

        seen_ids: set[str] = set()
        scraped_at = datetime.now(timezone.utc).isoformat()
        for match in _PRODUCT_RE.finditer(decoded):
            product_id = match.group("id")
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            product_name = self._decode_fragment(match.group("name")).strip()
            if not product_name:
                continue

            price = int(match.group("price")) / 100
            yield {
                "product_id": product_id,
                "product_name": product_name[:500],
                "category": None,
                "price": f"{price:.2f}",
                "currency": self.currency or next(iter(currencies), ""),
                "available": match.group("soldout") == "false",
                "url": f"https://take.app/{self.STORE_ALIAS}/p/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _flight_chunks(text: str) -> Iterable[str]:
        for match in _FLIGHT_CHUNK_RE.finditer(text):
            try:
                yield json.loads(match.group(1))
            except json.JSONDecodeError:
                logger.debug("could not decode take.app flight chunk", exc_info=True)

    @staticmethod
    def _decode_fragment(raw: str) -> str:
        try:
            return html.unescape(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            return html.unescape(raw)
