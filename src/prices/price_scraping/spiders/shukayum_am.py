"""Spider for Shukayum.am - https://shukayum.am/en/.

Shukayum is a WooCommerce storefront, but the public REST API returns
rest_disabled. Category HTML still exposes product blocks with product names,
permalinks, data-price and data-currency attributes, and WooCommerce
pagination. Re-verified live 2026-09-01.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORY_URLS = [
    "https://shukayum.am/en/product-category/mirg-ev-banjareghen/",
    "https://shukayum.am/en/product-category/katnamterq-ev-havkit/",
    "https://shukayum.am/en/product-category/msamterq/",
    "https://shukayum.am/en/product-category/dzuk-ev-tsovamterq/",
    "https://shukayum.am/en/product-category/npareghen/",
    "https://shukayum.am/en/product-category/hatsabulkeghen-ev-tkhvatsqner/",
    "https://shukayum.am/en/product-category/chipser-ev-sermer/",
    "https://shukayum.am/en/product-category/qaghtsraveniq/",
    "https://shukayum.am/en/product-category/surch-ev-tey/",
    "https://shukayum.am/en/product-category/ympeliqner/",
    "https://shukayum.am/en/product-category/saretsvats-mterq/",
]
_MAX_PAGES_PER_CATEGORY = 20
_PRICE_RE = re.compile(r"[\d\s,.\u00a0]+")


def _clean(text: object) -> str:
    return re.sub(
        r"\s+",
        " ",
        html.unescape(str(text or "")).replace("\u00a0", " "),
    ).strip()


class ShukayumAmSpider(scrapy.Spider):
    name = "shukayum_am"
    allowed_domains = ["shukayum.am"]
    currency = "AMD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_product_ids: set[str] = set()

    async def start(self):
        for url in _CATEGORY_URLS:
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                meta={"category_url": url, "page": 1},
            )

    def parse_category(self, response):
        category = _clean(
            " ".join(response.css(".category-title::text").getall())
            or " ".join(response.css("h1::text").getall())
        )
        if not category:
            category = response.meta["category_url"].rstrip("/").split("/")[-1]

        cards = response.css(".product-block")
        logger.info(
            "shukayum_am: %s page=%s cards=%d",
            category,
            response.meta["page"],
            len(cards),
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for card in cards:
            row = self._item(card, category, scraped_at)
            if row:
                yield row
                emitted += 1

        page = int(response.meta["page"])
        next_href = response.css(
            "a.next.page-numbers::attr(href), .woocommerce-pagination a.next::attr(href)"
        ).get()
        if emitted and next_href and page < _MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                response.urljoin(next_href),
                callback=self.parse_category,
                meta={
                    "category_url": response.meta["category_url"],
                    "page": page + 1,
                },
            )

    def _item(self, card, category: str, scraped_at: str) -> dict | None:
        name_link = card.css(".sproduct-name a")
        href = name_link.attrib.get("href") if name_link else card.css("a::attr(href)").get()
        product_id = _clean(
            card.css(".add-to-cart::attr(data-product_id), .add-to-cart::attr(value)").get()
        )
        if not product_id and href:
            product_id = href.rstrip("/").split("/")[-1]
        if not product_id or product_id in self.seen_product_ids:
            return None

        name = _clean(" ".join(name_link.css("::text").getall()))
        price_el = card.css(".price[data-price]")
        price = self._price(price_el.attrib.get("data-price") if price_el else None)
        if price is None:
            price = self._price(" ".join(card.css(".price ::text").getall()))
        if not name or price is None:
            return None

        currency = _clean(price_el.attrib.get("data-currency") if price_el else None).upper()
        if currency not in {"AMD"}:
            currency = self.currency

        self.seen_product_ids.add(product_id)
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": currency,
            "available": True,
            "url": href or "",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _price(text: str | None) -> str | None:
        match = _PRICE_RE.search(_clean(text))
        if not match:
            return None
        value = re.sub(r"\D", "", match.group(0))
        if not value:
            return None
        number = int(value)
        if number <= 0:
            return None
        return str(number)
