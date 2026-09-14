"""Costa Rica cigarette prices from Jaco Wine & Liquor's WooCommerce catalogue."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)
_START_URL = "https://jacoliquor.com/product-category/cigarros/cigarrillos/"
_CARD_SEL = "ul.products > li.product"
_POST_ID_RE = re.compile(r"(?:^|\s)post-(\d+)(?:\s|$)")
_USD_PRICE_RE = re.compile(r"^\$\s*([0-9]+(?:\.[0-9]{3})*,[0-9]{2})$")


def _parse_usd_price(text: str) -> str | None:
    match = _USD_PRICE_RE.fullmatch(" ".join(text.split()))
    return match.group(1).replace(".", "").replace(",", ".") if match else None


class JacoLiquorCrSpider(scrapy.Spider):
    name = "jacoliquor_cr"
    allowed_domains = ["jacoliquor.com", "www.jacoliquor.com"]
    currency = "USD"
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
            price = _parse_usd_price(price_text)
            if not title or not href or not post_match or price is None:
                continue
            yielded += 1
            yield {
                "product_id": post_match.group(1), "product_name": title[:500],
                "category": "tobacco", "price": price, "currency": self.currency,
                "available": "outofstock" not in card.attrib.get("class", "").lower(),
                "url": response.urljoin(href), "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info("jacoliquor_cr: cards=%d yielded=%d", len(response.css(_CARD_SEL)), yielded)
        for href in response.css("a.next.page-numbers::attr(href), a[rel='next']::attr(href)").getall():
            yield response.follow(href, callback=self.parse_listing)
