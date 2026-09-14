"""Spider for Arji Market - https://arjimarket.am/en/.

Arji Market category pages render product cards server-side. Re-verified live
2026-09-01: bread, ham and milk category pages exposed product-detail URLs,
names, AMD prices, cart ids for in-stock rows and explicit unavailable labels.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://arjimarket.am"
_CATEGORY_PATHS = [
    "/en/hac/",
    "/en/hjuther/",
    "/en/djur/",
    "/en/havi-mis-tchut/",
    "/en/ephats-ershik/",
    "/en/xozapuxt/",
    "/en/kendani-dzuk/",
    "/en/hav-tchut/",
    "/en/bandjareghen-mirg-hataptugh/",
    "/en/dzithaptugh/",
    "/en/mrger/",
    "/en/bandjareghen/",
    "/en/kanachi/",
    "/en/qaghcraveniq-4100/",
    "/en/kath-och-kathnajin-ympeliq/",
    "/en/karag-margarin/",
    "/en/dzu/",
    "/en/makaronner/",
    "/en/hndkadzavar-9519/",
    "/en/brindz/",
    "/en/aratsaghki-dzeth/",
    "/en/agh/",
]
_MAX_PAGES_PER_CATEGORY = 20
_PRICE_RE = re.compile(r"[\d\s,.\u00a0]+")


def _clean(text: object) -> str:
    return re.sub(
        r"\s+",
        " ",
        html.unescape(str(text or "")).replace("\u00a0", " "),
    ).strip()


class ArjiMarketAmSpider(scrapy.Spider):
    name = "arji_market_am"
    allowed_domains = ["arjimarket.am"]
    currency = "AMD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
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
        for path in _CATEGORY_PATHS:
            yield scrapy.Request(
                urljoin(_BASE, path),
                callback=self.parse_category,
                meta={"category_path": path, "page": 1},
            )

    def parse_category(self, response):
        category = _clean(response.css("#category::text").get())
        if not category:
            category = response.meta["category_path"].strip("/").split("/")[-1]

        cards = response.css(".product_card_flex-box__item")
        logger.info(
            "arji_market_am: %s page=%s cards=%d",
            category,
            response.meta["page"],
            len(cards),
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for card in cards:
            row = self._item(card, response, category, scraped_at)
            if row:
                yield row
                emitted += 1

        page = int(response.meta["page"])
        next_href = response.css(
            ".pagination a[rel=next]::attr(href), .pagination a.next::attr(href)"
        ).get()
        if emitted and next_href and page < _MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                urljoin(response.url, next_href),
                callback=self.parse_category,
                meta={
                    "category_path": response.meta["category_path"],
                    "page": page + 1,
                },
            )

    def _item(self, card, response, category: str, scraped_at: str) -> dict | None:
        href = card.css(".product_card_info > a::attr(href), .product_card_img a::attr(href)").get()
        product_id = _clean(
            card.css(".add-to-cart::attr(data-id), .add-to-favorites::attr(data-id)").get()
        )
        if not product_id and href:
            product_id = href.strip("/").split("/")[-1]
        if not product_id or product_id in self.seen_product_ids:
            return None

        name = _clean(
            " ".join(card.css(".product_card_info > a::text").getall())
            or card.css(".product_card_img img::attr(alt)").get()
        )
        price = self._price(" ".join(card.css(".product_card_info_num::text").getall()))
        if not name or price is None:
            return None

        self.seen_product_ids.add(product_id)
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": not bool(card.css(".product_not_available")),
            "url": urljoin(response.url, href or f"/en/products/{product_id}/"),
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
