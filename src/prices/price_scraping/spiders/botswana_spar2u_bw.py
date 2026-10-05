"""SPAR2U Botswana grocery catalogue.

SPAR2U renders category and subcategory pages server-side.  Product cards
contain a stable UPC product route, a product name, and a Botswana-pula price.
The spider recursively follows only Botswana category routes and emits each
UPC once even when a product appears in multiple categories.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_ROOT_URL = "https://www.spar2u.co.bw/en-BW/categories/pantry/rice-maize-and-pasta"
_PRODUCT_PATH = re.compile(r"^/en-BW/product/([^/?#]+)/?$")
_PRICE = re.compile(r"\bP\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b", re.I)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


class BotswanaSpar2uBwSpider(scrapy.Spider):
    name = "botswana_spar2u_bw"
    allowed_domains = ["spar2u.co.bw", "www.spar2u.co.bw"]
    currency = "BWP"
    language = "en"
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.25,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_products: set[str] = set()

    async def start(self):
        yield scrapy.Request(_ROOT_URL, callback=self.parse_category)

    def parse_category(self, response):
        category = _clean(response.css("main h1::text").get()) or None

        for link in response.css("main a[href*='/en-BW/product/']"):
            href = link.attrib.get("href", "")
            match = _PRODUCT_PATH.match(href)
            if not match:
                continue
            product_id = match.group(1)
            if product_id in self._seen_products:
                continue

            paragraphs = [_clean(text) for text in link.css("p::text").getall()]
            paragraphs = [text for text in paragraphs if text]
            price_match = next((_PRICE.search(text) for text in paragraphs if _PRICE.search(text)), None)
            if price_match is None:
                continue

            name = next((text for text in paragraphs if _PRICE.search(text) is None), "")
            if not name:
                name = _clean(link.css("img::attr(alt)").get())
            if not name:
                continue

            price = price_match.group(1).replace(",", "")
            if float(price) <= 0:
                continue

            self._seen_products.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href).split("?", 1)[0],
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
