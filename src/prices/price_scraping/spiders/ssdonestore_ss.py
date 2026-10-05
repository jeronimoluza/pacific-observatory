"""Consumer-product listings from SSD One Store's public WooCommerce pages."""

from __future__ import annotations

import re
import logging
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod


logger = logging.getLogger(__name__)


_START_URL = "https://ssdonestore.com/shop/"
_CARD_SEL = ".product-item.product"
_POST_ID_RE = re.compile(r"(?:^|\s)post-(\d+)(?:\s|$)")
_PRICE_RE = re.compile(r"^\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)$")


def _playwright_meta():
    return {
        "playwright": True,
        "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
        "playwright_page_methods": [
            PageMethod("wait_for_selector", _CARD_SEL, timeout=30000),
        ],
    }


class SsdonestoreSsSpider(scrapy.Spider):
    name = "ssdonestore_ss"
    allowed_domains = ["ssdonestore.com", "www.ssdonestore.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_START_URL, callback=self.parse_listing, meta=_playwright_meta())

    def parse_listing(self, response):
        rendered_cards = len(response.css(_CARD_SEL))
        yielded = 0
        for card in response.css(_CARD_SEL):
            title = (
                card.css(
                    "h2.product-title a::text, "
                    ".woocommerce-loop-product__title::text, "
                    "h2 a[href*='/product/']::text, "
                    "h3 a[href*='/product/']::text"
                ).get()
                or ""
            ).strip()
            href = card.css('a[href*="/product/"]::attr(href)').get()
            post_match = _POST_ID_RE.search(card.attrib.get("class", ""))
            price_text = " ".join(card.css(".price ::text, .price::text").getall()).strip()
            price_match = _PRICE_RE.match(price_text)

            # Variable products display a range. Keep only a public exact SKU
            # price, rather than silently using the lower bound of a range.
            if not title or not href or not post_match or not price_match:
                continue

            yielded += 1
            yield {
                "product_id": post_match.group(1),
                "product_name": title[:500],
                "category": None,
                "price": price_match.group(1).replace(",", ""),
                "currency": self.currency,
                "available": "outofstock" not in card.attrib.get("class", "").lower(),
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            "ssdonestore_ss: rendered_cards=%d yielded=%d url=%s",
            rendered_cards,
            yielded,
            response.url,
        )

        for href in response.css('a.next.page-numbers::attr(href), a[rel="next"]::attr(href)').getall():
            yield response.follow(href, self.parse_listing, meta=_playwright_meta())
