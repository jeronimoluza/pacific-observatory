"""
Spider for HaloDili ZD Supermarket (Timor-Leste) — https://halodili.com/zdsupermarket

Magento 2 server-rendered listing pages. Product cards (name, price, id) are
visible in raw HTML — no JS required.

Strategy:
  1. Start at the ZD Supermarket category listing (4,601 items).
  2. Extract up to 20 product cards per listing page.
  3. Follow the paginator next-page link (a[title="Next"]) to walk all pages.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"[\d.]+")


class HalodiliSpider(scrapy.Spider):
    name = "halodili"
    allowed_domains = ["halodili.com"]
    currency = "USD"

    START_URLS = ["https://halodili.com/zdsupermarket"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    async def start(self):
        for url in self.START_URLS:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        cards = response.css("li.item.product.product-item")
        scraped_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"halodili: {response.url} → {len(cards)} cards")

        for card in cards:
            product_id = card.css("input[name='product']::attr(value)").get()
            if not product_id or product_id in self.seen_ids:
                continue
            self.seen_ids.add(product_id)

            name = (
                card.css("a.product-item-link::text").get()
                or card.css("img::attr(alt)").get()
                or ""
            ).strip()

            price_text = card.css("span.price::text").get("").strip()
            m = PRICE_RE.search(price_text.replace(",", ""))
            price = m.group() if m else None

            url = card.css("a.product-item-photo::attr(href)").get()

            if not name or not price:
                logger.warning(
                    f"halodili: missing name/price for product_id={product_id}"
                )
                continue

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": url or response.url,
                "scraped_at_utc": scraped_at,
            }

        next_url = response.css("a[title='Next']::attr(href)").get()
        if next_url:
            yield scrapy.Request(next_url, callback=self.parse_listing)
