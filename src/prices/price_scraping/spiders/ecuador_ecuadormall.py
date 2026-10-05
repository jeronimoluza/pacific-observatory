"""EcuadorMall's browser-reachable food and beverage catalogue."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import scrapy
from scrapy_playwright.page import PageMethod


CATALOG_URL = "https://www.ecuadormall.com/catalog/default.php?cPath=12"
_PRODUCT_LINK = 'a.Menu2[href*="product_info.php?products_id="]'
_PRICE_RE = re.compile(r"^\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)$")


def _clean(values) -> str:
    return " ".join(" ".join(values).split())


def _canonical_product(href: str) -> tuple[str, str] | None:
    parsed = urlsplit(href)
    product_ids = parse_qs(parsed.query).get("products_id", [])
    if len(product_ids) != 1 or not product_ids[0].isdigit():
        return None
    product_id = product_ids[0]
    url = urlunsplit(
        (
            "https",
            "www.ecuadormall.com",
            "/catalog/product_info.php",
            urlencode({"products_id": product_id}),
            "",
        )
    )
    return product_id, url


def parse_products(response, scraped_at: str | None = None):
    """Yield complete F&B rows from the legacy four-column product grids."""
    usd_selected = response.css(
        'select[name="currency"] option[value="USD"][selected]'
    )
    if not usd_selected:
        return

    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()

    for table in response.css('table[width="100%"]'):
        links = table.css(_PRODUCT_LINK)
        prices = table.css("span.Texto2Bold::text").getall()
        if not links or len(links) != len(prices):
            continue

        for link, price_text in zip(links, prices):
            product = _canonical_product(link.attrib.get("href", ""))
            name = _clean(link.css("::text").getall())
            price_match = _PRICE_RE.match(price_text.strip())
            if not product or not name or not price_match:
                continue

            product_id, url = product
            if product_id in seen:
                continue
            try:
                price = Decimal(price_match.group(1).replace(",", ""))
            except InvalidOperation:
                continue
            if price <= 0:
                continue

            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Food and Beverages",
                "price": format(price, "f"),
                "currency": "USD",
                "country": "Ecuador",
                "sector": "consumer_goods",
                "available": True,
                "url": url,
                "language": "en",
                "scraped_at_utc": scraped_at,
            }


class EcuadorEcuadorMallSpider(scrapy.Spider):
    name = "ecuador_ecuadormall"
    allowed_domains = ["ecuadormall.com", "www.ecuadormall.com"]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        # Direct requests previously failed before HTTP; Chromium transport is verified.
        yield scrapy.Request(
            CATALOG_URL,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", _PRODUCT_LINK, timeout=45000),
                ],
            },
        )

    def parse(self, response):
        yield from parse_products(response)
