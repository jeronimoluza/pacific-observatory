"""Kaze Market (Burundi) WooCommerce HTML product-card scraper.

Bujumbura grocery store (Burundi phone +257 68 076 049 in the footer),
food/beverage-only WooCommerce catalogue -- every product_cat observed
(alimentaire, biere, les-farines, les-produits-frais, les-boissons,
les-epiceries-sucrees, les-huiles, riz-pates-et-graines, sucre, graines,
riz) is COICOP 01/02. The Store API (/wp-json/wc/store/v1/products) 404s,
so this scrapes the server-rendered shop-loop HTML instead, same pattern
as obba_mc but this theme's markup has no <bdi> wrapper and a plain <a>
around the loop link (verified via curl_cffi-free plain curl -- no
anti-bot on this host).

CURRENCY CAVEAT: prices are denominated in EUR, not BIF (Burundi's
currency) -- same population as tchitunga_cg / market242_cg (Congo
Republic diaspora-style grocery sites priced in EUR for a buyer who pays
from abroad while goods are delivered locally). May carry a
remittance-service markup rather than being a 1:1 organic local retail
price. Emitted as EUR (the site's own stated currency) per the
"site's stated currency wins over the country default" convention.

Enumerability verified 2026-09-11: /boutique/page/1/ vs /boutique/page/2/
returned 9 distinct product URLs each, 0 overlap. 8 total pages via
a.next.page-numbers pagination -> ~70 products.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


class KazemarketBiSpider(scrapy.Spider):
    name = "kazemarket_bi"
    allowed_domains = ["www.kazemarket.com", "kazemarket.com"]
    currency = "EUR"
    language = "fr"
    start_urls = ["https://www.kazemarket.com/boutique/page/1/"]

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
        self.logger.info("CARDS=%d" % len(response.css("li.product")))
        for card in response.css("li.product"):
            post_id = card.attrib.get("id", "").replace("post-", "")
            name = card.css(".woocommerce-loop-product__title::text").get()
            url = card.css("a::attr(href)").get()
            price_text = "".join(
                card.css(".price .woocommerce-Price-amount ::text").getall()
            )
            category = self._category(card)
            price = self._price(price_text)
            self.logger.info("NAME=%r PRICE_TEXT=%r PRICE=%r" % (name, price_text, price))
            if not (name and price):
                continue
            yield {
                "product_id": (post_id or url or "").strip(),
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": "instock" in (card.attrib.get("class") or ""),
                "url": urljoin(response.url, url) if url else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        for href in response.css("a.next.page-numbers::attr(href)").getall():
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
