"""OBBA (Monaco) WooCommerce HTML product-card scraper.

Fine-grocery / butcher / fishmonger, Monaco-domiciled (57 rue Grimaldi,
98000 Monaco -- confirmed via the site's own /contact/ page). Standard
WooCommerce shop-loop theme; the Store API (/wp-json/wc/store/v1/products)
returns a WordPress 500 error, so this scrapes the server-rendered
category/shop HTML instead (li.product cards, same markup shape as
the_good_meat_ph but <li> not <article>).
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


class ObbaMcSpider(scrapy.Spider):
    name = "obba_mc"
    allowed_domains = ["www.obba.mc", "obba.mc"]
    currency = "EUR"
    language = "fr"
    start_urls = ["https://www.obba.mc/boutique/page/1/"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "COOKIES_ENABLED": False,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("li.product"):
            product_id = card.attrib.get("id", "").replace("post-", "")
            name = card.css(".woocommerce-loop-product__title::text").get()
            url = card.css("a.woocommerce-LoopProduct-link::attr(href)").get()
            price_text = card.css(".woocommerce-Price-amount bdi::text").get()
            category = self._category(card)
            price = self._price(price_text)
            if not (name and price):
                continue
            yield {
                "product_id": (product_id or url or "").strip(),
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": "instock" in (card.attrib.get("class") or ""),
                "url": urljoin(response.url, url) if url else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        for href in response.css("a.next::attr(href), a.page-numbers::attr(href)").getall():
            if href:
                yield response.follow(href, callback=self.parse)

    @staticmethod
    def _price(raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = raw.replace("\xa0", "").replace(",", ".")
        cleaned = re.sub(r"[^0-9.]", "", cleaned)
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
