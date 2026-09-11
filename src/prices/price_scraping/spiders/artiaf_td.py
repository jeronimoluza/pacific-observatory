"""Artiaf (Chad) -- https://www.artiaf.com/. PrestaShop, no open webservice
API (/api/products 401s without a key -- presumably why the earlier triage
marked this NEEDS-CUSTOM-CRAWLER). The public category HTML is the
enumerable surface instead.

Not built on the shared _prestashop_base.py: that base's generic category-
link recursion + name/price selectors mismatched product cards to the wrong
name/url on this theme (verified: yielded 1 item with a name/url pair from
two different products). This site's catalog is small and flat (10
categories, no subcategory nesting seen), so a fixed category list with a
direct `[data-id-product]` card selector is simpler and correct.

FCFA prices confirmed as XAF (itemprop=priceCurrency on a PDP's JSON-LD) for
the Central African zone, matching countries.yaml's Chad default.
Page family: listing only -- price and name are both present on the
category grid; PDPs are never fetched.
"""

from __future__ import annotations

from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

CATEGORIES = [
    "22-epices-africaines",
    "31-minceur-naturelle",
    "32-vitalite-naturelle",
    "38-cosmetiques-naturels",
    "59-pagnes-divers",
    "63-chiganvy",
    "65-vlisco",
    "66-bogolan",
    "67-bijoux",
    "68-sacs-pagne",
]


class ArtiafTdSpider(scrapy.Spider):
    name = "artiaf_td"
    allowed_domains = ["artiaf.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for cat in CATEGORIES:
            yield scrapy.Request(
                f"https://www.artiaf.com/fr/{cat}",
                callback=self.parse_listing,
                meta={"cat": cat},
            )

    def parse_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        cat = response.meta["cat"]
        for card in soup.select("[data-id-product]"):
            name_el = card.select_one("[itemprop=name]")
            price_el = card.select_one("[itemprop=price]")
            link = card.select_one("a[href]")
            if not name_el or not price_el or not link:
                continue
            price = price_el.get("content") or price_el.get_text(strip=True)
            name = name_el.get_text(strip=True)
            url = link.get("href")
            if not name or not price or not url:
                continue
            try:
                if float(price) == 0:
                    continue
            except (TypeError, ValueError):
                continue
            yield {
                "product_id": card.get("data-id-product"),
                "product_name": name[:500],
                "category": cat,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
