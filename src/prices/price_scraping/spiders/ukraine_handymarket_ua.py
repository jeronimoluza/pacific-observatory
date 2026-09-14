"""Ukraine HandyMarket's browser-reachable tools catalogue."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

import scrapy
from scrapy_playwright.page import PageMethod


CATALOG_URL = "https://handymarket.com.ua/uk/instrumenty/vspomagatelnye"
_PRODUCT_CARD = "#product-list > .item-product"
_PRODUCT_ID_RE = re.compile(r"^\s*Код\s+(\S+)\s*$")
_PRICE_RE = re.compile(
    r"^\s*(?:Від\s+)?([0-9][0-9\s]*(?:[.,][0-9]{1,2})?)\s*грн\."
)


def _clean(values) -> str:
    return " ".join(" ".join(values).split())


def _canonical_url(raw_url: str) -> str | None:
    parsed = urlsplit(raw_url)
    if parsed.scheme != "https" or parsed.netloc != "handymarket.com.ua":
        return None
    if not parsed.path.startswith("/uk/") or parsed.path == "/uk/":
        return None
    return urlunsplit(("https", "handymarket.com.ua", parsed.path, "", ""))


def parse_products(response, scraped_at: str | None = None):
    """Yield current retail prices from rendered HandyMarket product cards."""
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()

    for card in response.css(_PRODUCT_CARD):
        product_id_match = _PRODUCT_ID_RE.match(
            _clean(card.css(".article::text").getall())
        )
        name = _clean(card.css(".name-product::text").getall())
        price_match = _PRICE_RE.match(_clean(card.css(".new-price::text").getall()))
        url = _canonical_url(card.attrib.get("data-href", ""))
        if not product_id_match or not name or not price_match or not url:
            continue

        product_id = product_id_match.group(1)
        if product_id in seen:
            continue
        try:
            price = Decimal(price_match.group(1).replace(" ", "").replace(",", "."))
        except InvalidOperation:
            continue
        if price <= 0:
            continue

        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": "Auxiliary tools",
            "price": format(price, "f"),
            "currency": "UAH",
            "country": "Ukraine",
            "sector": "consumer_goods",
            "available": True,
            "url": url,
            "language": "uk",
            "scraped_at_utc": scraped_at,
        }


class UkraineHandyMarketUaSpider(scrapy.Spider):
    name = "ukraine_handymarket_ua"
    allowed_domains = ["handymarket.com.ua"]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 1,
    }

    def _request(self, url: str):
        return scrapy.Request(
            url,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", _PRODUCT_CARD, timeout=45000),
                ],
            },
        )

    async def start(self):
        yield self._request(CATALOG_URL)

    def parse(self, response):
        yield from parse_products(response)
        next_url = response.css(
            'nav[aria-label="Page navigation example"] a.page-link.next.active::attr(href)'
        ).get()
        if next_url:
            yield self._request(response.urljoin(next_url))
