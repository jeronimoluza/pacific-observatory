"""Cigar and accessory prices from Dominican Cigars' WooCommerce catalogue."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)
_START_URL = "https://dominicancigars.com.do/shop/"
_CARD_SEL = "ul.products > li.product"
_POST_ID_RE = re.compile(r"(?:^|\s)post-(\d+)(?:\s|$)")
_DOP_PRICE_RE = re.compile(r"^RD\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)$")


def _parse_dop_price(text: str) -> str | None:
    match = _DOP_PRICE_RE.fullmatch(" ".join(text.split()))
    return match.group(1).replace(",", "") if match else None


class DominicanCigarsDoSpider(scrapy.Spider):
    name = "dominicancigars_do"
    allowed_domains = ["dominicancigars.com.do", "www.dominicancigars.com.do"]
    currency = "DOP"
    language = "es"

    async def start(self):
        yield scrapy.Request(_START_URL, callback=self.parse_listing)

    def parse_listing(self, response):
        yielded = 0
        for card in response.css(_CARD_SEL):
            title = (card.css("h2.woocommerce-loop-product__title::text").get() or "").strip()
            href = card.css("a.woocommerce-LoopProduct-link::attr(href)").get()
            post_match = _POST_ID_RE.search(card.attrib.get("class", ""))
            price_text = "".join(card.css("span.price bdi ::text, span.price bdi::text").getall()).strip()
            price = _parse_dop_price(price_text)
            if not title or not href or not post_match or price is None:
                continue
            yielded += 1
            yield {
                "product_id": post_match.group(1), "product_name": title[:500],
                "category": "tobacco/accessories", "price": price, "currency": self.currency,
                "available": "outofstock" not in card.attrib.get("class", "").lower(),
                "url": response.urljoin(href), "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info("dominicancigars_do: cards=%d yielded=%d", len(response.css(_CARD_SEL)), yielded)
        for href in response.css("a.next.page-numbers::attr(href), a[rel='next']::attr(href)").getall():
            yield response.follow(href, callback=self.parse_listing)
