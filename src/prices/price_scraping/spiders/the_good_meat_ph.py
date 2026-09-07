"""The Good Meat Philippines HTML product-card scraper."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


class TheGoodMeatPhSpider(scrapy.Spider):
    name = "the_good_meat_ph"
    allowed_domains = ["thegoodmeat.ph"]
    currency = "PHP"
    language = "en"
    start_urls = ["https://thegoodmeat.ph/shops/"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "COOKIES_ENABLED": False,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("article.product"):
            product_id = card.attrib.get("id", "").replace("post-", "")
            name = card.css(".woocommerce-loop-product__title::text").get()
            url = card.css("a.woocommerce-LoopProduct-link::attr(href)").get()
            price_text = card.css(".woocommerce-Price-amount bdi::text").get()
            sku = card.css(".add_to_cart_button::attr(data-product_sku)").get()
            category = self._category(card)
            price = self._price(price_text)
            if not (name and price):
                continue
            yield {
                "product_id": (sku or product_id).strip(),
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": "instock" in (card.attrib.get("class") or ""),
                "url": urljoin(response.url, url) if url else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        for href in response.css("a.page-numbers::attr(href)").getall():
            if href:
                yield response.follow(href, callback=self.parse)

    @staticmethod
    def _price(raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = re.sub(r"[^0-9.]", "", raw)
        if not cleaned:
            return None
        try:
            return f"{float(cleaned):.2f}"
        except ValueError:
            return None

    @staticmethod
    def _category(card) -> str | None:
        classes = card.attrib.get("class") or ""
        cats = []
        for value in classes.split():
            if value.startswith("product_cat-"):
                cats.append(value.removeprefix("product_cat-").replace("-", " "))
        return " > ".join(cats) or None
