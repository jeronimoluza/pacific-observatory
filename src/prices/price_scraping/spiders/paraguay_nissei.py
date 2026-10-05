"""Paraguay Nissei's browser-rendered multi-category catalogue."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

import scrapy
from scrapy_playwright.page import PageMethod


CATALOG_URL = "https://nissei.com/py/"
_PRODUCT_CARD = ".product-item-info"
_PRICE_RE = re.compile(r"^Gs\.\s*([0-9][0-9.]*)$")


def _clean(values) -> str:
    return " ".join(" ".join(values).split())


def _canonical_product_url(href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme != "https" or parsed.netloc.lower() != "nissei.com":
        return None
    if not parsed.path.startswith("/py/") or parsed.path == "/py/":
        return None
    return urlunsplit(("https", "nissei.com", parsed.path.rstrip("/"), "", ""))


def parse_products(response, scraped_at: str | None = None):
    """Yield unique current-price rows from Nissei's rendered Magento cards."""
    title = _clean(response.css("title::text").getall())
    footer = _clean(response.css("footer ::text").getall())
    if "Paraguay" not in title or "Nissei Ciudad del Este" not in footer:
        return

    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()

    for card in response.css(_PRODUCT_CARD):
        price_boxes = card.css('.price-box[data-product-id]')
        if not price_boxes:
            continue
        box = price_boxes[0]
        product_id = box.attrib.get("data-product-id", "").strip()
        name = _clean(card.css(".product-item-name ::text").getall())
        href = card.css("a.product-item-link::attr(href)").get("")
        url = _canonical_product_url(response.urljoin(href))
        price_text = _clean(
            box.css('[data-price-type="finalPrice"] .price::text').getall()
        )
        match = _PRICE_RE.fullmatch(price_text)

        if (
            not product_id.isdigit()
            or product_id in seen
            or not name
            or not url
            or not match
        ):
            continue
        price = Decimal(match.group(1).replace(".", ""))
        if price <= 0:
            continue

        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": "Multi-category retail",
            "price": format(price, "f"),
            "currency": "PYG",
            "country": "Paraguay",
            "sector": "consumer_goods",
            "available": True,
            "url": url,
            "language": "es",
            "scraped_at_utc": scraped_at,
        }


class ParaguayNisseiSpider(scrapy.Spider):
    name = "paraguay_nissei"
    allowed_domains = ["nissei.com"]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 1,
    }

    async def start(self):
        yield scrapy.Request(
            CATALOG_URL,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod(
                        "wait_for_selector",
                        f'{_PRODUCT_CARD} [data-price-type="finalPrice"]',
                        timeout=45000,
                    ),
                ],
            },
        )

    def parse(self, response):
        yield from parse_products(response)
