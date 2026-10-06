"""Nawak Import (Grand Case, Saint-Martin French part) -- https://nawakimport.com/.

Odoo website_sale storefront, server-rendered, no anti-bot at chrome124.
Listing /en/shop/page/N: 20 cards per page, ~4,876 products. Prices are EUR
(itemprop priceCurrency), rendered as whole euros.
Listing-only: the spider never fetches a PDP.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import scrapy


class NawakimportMfSpider(scrapy.Spider):
    name = "nawakimport_mf"
    allowed_domains = ["nawakimport.com"]
    currency = "EUR"
    language = "en"
    max_pages = 300

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "COOKIES_ENABLED": False,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            "https://nawakimport.com/en/shop", callback=self.parse, cb_kwargs={"page": 1}
        )

    def parse(self, response, page):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css("div.tp-product-item")
        for card in cards:
            item = self._parse_card(response, card, scraped_at)
            if item:
                yield item
        if cards and page < self.max_pages:
            yield response.follow(
                f"/en/shop/page/{page + 1}", callback=self.parse, cb_kwargs={"page": page + 1}
            )

    def _parse_card(self, response, card, scraped_at):
        href = card.css('a[itemprop="name"]::attr(href)').get() or card.css(
            'a[itemprop="url"]::attr(href)'
        ).get()
        name = card.css('a[itemprop="name"]::attr(title)').get() or card.css(
            'a[itemprop="name"]::text'
        ).get()
        price = card.css('span[itemprop="price"]::text').get() or card.css(
            "span.oe_currency_value::text"
        ).get()
        if not href or not name or not price:
            return None
        name = " ".join(name.split())
        if "NE PAS VENDRE" in name.upper():
            return None
        try:
            value = float(price.replace(",", ""))
        except ValueError:
            return None
        if value <= 0:
            return None
        url = urlunparse(urlparse(response.urljoin(href))._replace(query="", fragment=""))
        m = re.search(r"-(\d+)$", url)
        pid = card.attrib.get("data-product-template-id") or (m.group(1) if m else url)
        return {
            "product_id": str(pid),
            "product_name": name[:500],
            "price": f"{value:.2f}",
            "currency": self.currency,
            "category": None,
            "url": url,
            "language": self.language,
            "store": "Nawak Import",
            "scraped_at_utc": scraped_at,
        }
