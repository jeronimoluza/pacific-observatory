"""ShoppingAZ's browser-reachable Azerbaijan consumer-goods catalogue."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urldefrag, urlsplit

import scrapy
from scrapy_playwright.page import PageMethod


CATALOG_URL = "https://shoppingaz.az/en/mehsullar/"
_PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*₼")


def _clean(values) -> str:
    return " ".join(" ".join(values).split())


def parse_products(response, scraped_at: str | None = None):
    """Yield complete, positive-AZN rows from ShoppingAZ product cards."""
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()

    for card in response.css(".product-item[data-id]"):
        product_id = (card.attrib.get("data-id") or "").strip()
        name = _clean(card.css("h3.product-item__header ::text").getall())
        price_text = _clean(
            card.css(".product-item__price_aktual ::text").getall()
        )
        price_match = _PRICE_RE.search(price_text)
        href = card.xpath("./a[1]/@href").get()
        url = urldefrag(response.urljoin(href or ""))[0]
        parsed = urlsplit(url)

        if (
            not product_id.isdigit()
            or product_id in seen
            or not name
            or not price_match
            or parsed.scheme != "https"
            or parsed.netloc != "shoppingaz.az"
            or not parsed.path.startswith("/en/")
        ):
            continue

        try:
            price = Decimal(price_match.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        if price <= 0:
            continue

        seen.add(product_id)
        classes = set((card.attrib.get("class") or "").split())
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": _clean(card.css("a.meta-cat ::text").getall()) or None,
            "seller": _clean(card.css("a.meta-brand ::text").getall()) or None,
            "price": format(price, "f"),
            "currency": "AZN",
            "country": "Azerbaijan",
            "sector": "consumer_goods",
            "available": "outofstock" not in classes,
            "url": url,
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class AzerbaijanShoppingAZSpider(scrapy.Spider):
    name = "azerbaijan_shoppingaz"
    allowed_domains = ["shoppingaz.az"]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 2,
    }

    def _request(self, url: str):
        return scrapy.Request(
            url,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", ".product-item[data-id]", timeout=45000),
                ],
            },
        )

    async def start(self):
        yield self._request(CATALOG_URL)

    def parse(self, response):
        yield from parse_products(response)
        next_url = response.css("a.next.page-numbers::attr(href)").get()
        if next_url:
            yield self._request(urldefrag(response.urljoin(next_url))[0])
