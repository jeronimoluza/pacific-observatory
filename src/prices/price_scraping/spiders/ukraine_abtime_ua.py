"""Abtime Ukraine watch listings from the server-rendered product grid."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_START_URL = "https://abtime.com.ua/"
_CARD_SEL = ".sc-module-item"
_ID_RE = re.compile(r"^[1-9][0-9]*$")
_PRICE_RE = re.compile(r"^([1-9][0-9\s\u00a0\u202f]*)\s*грн$", re.IGNORECASE)
_PRODUCT_PATH_RE = re.compile(r"^[^/?#]+(?:/[^/?#]+)+/?$")


def _parse_price(text: str) -> str | None:
    """Return only an exact, positive whole-UAH price from the price node."""
    match = _PRICE_RE.fullmatch(" ".join((text or "").split()))
    if not match:
        return None
    amount = re.sub(r"[\s\u00a0\u202f]", "", match.group(1))
    return amount if int(amount) > 0 else None


class UkraineAbtimeUaSpider(scrapy.Spider):
    name = "ukraine_abtime_ua"
    allowed_domains = ["abtime.com.ua", "www.abtime.com.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_START_URL, callback=self.parse_listing)

    def parse_listing(self, response):
        page_text = " ".join(response.css("body ::text").getall()).lower()
        if response.url.split("/", 3)[2].lower() not in {"abtime.com.ua", "www.abtime.com.ua"}:
            logger.warning("ukraine_abtime_ua: unexpected host %s", response.url)
            return
        if "україн" not in page_text and "uk-ua" not in response.text.lower():
            logger.warning("ukraine_abtime_ua: Ukraine locality marker absent")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        seen_ids: set[str] = set()
        yielded = 0
        for card in response.css(_CARD_SEL):
            product_id = (card.css('input[name="product_id"]::attr(value)').get() or "").strip()
            title_node = card.css(".sc-module-title")
            href = (title_node.attrib.get("href", "") if title_node else "").strip()
            name = " ".join(title_node.css("::text").getall()).strip() if title_node else ""
            price = _parse_price(card.css(".sc-module-price::text").get() or "")
            if not (_ID_RE.fullmatch(product_id) and product_id not in seen_ids):
                continue
            if not (name and _PRODUCT_PATH_RE.fullmatch(href) and price):
                continue
            seen_ids.add(product_id)
            yielded += 1
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "watches",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info("%s: cards=%d yielded=%d", self.name, len(response.css(_CARD_SEL)), yielded)
