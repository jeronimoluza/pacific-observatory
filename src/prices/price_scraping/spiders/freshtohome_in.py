"""
Spider for FreshToHome (India, specialty-food: meat/seafood/eggs) -
https://www.freshtohome.com/

CrawlSpider Pattern A — server-rendered HTML (Magento-family storefront).
Category listing pages are scoped per delivery city
(/buy-fish-meat-online/products/<city>); PDPs embed a schema.org Product
JSON-LD block with priceCurrency + price (no data-price-amount / og:price
meta on this theme, so JSON-LD is the only price surface). Scoped to one
representative city (Bangalore) — the catalog structure/operator is the
same nationwide, and crawling every city would just re-scrape near-identical
SKUs under different URLs.
"""

import json
import logging
import re
from typing import Optional

from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)

_LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def _parse_product_ldjson(text: str) -> Optional[dict]:
    for m in _LDJSON_RE.finditer(text):
        try:
            data = json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue
        return data
    return None


class FreshtohomeInSpider(CrawlSpider):
    name = "freshtohome_in"
    allowed_domains = ["freshtohome.com", "www.freshtohome.com"]
    start_urls = [
        "https://www.freshtohome.com/buy-fish-meat-online/products/bangalore",
    ]
    currency = "INR"

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/buy-fish-meat-online/products/bangalore/[a-z0-9\-]+\.html$",
            ),
            callback="parse_product",
            follow=False,
        ),
    )

    def parse_product(self, response):
        data = _parse_product_ldjson(response.text)
        if not data:
            logger.warning(
                f"Could not extract JSON-LD product data from {response.url}"
            )
            return

        offers = data.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            logger.warning(f"No offers block in JSON-LD for {response.url}")
            return

        price = offers.get("price")
        if price is None:
            return
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return
        if price_val <= 0:
            return

        name = (data.get("name") or "").strip()
        if not name:
            return

        yield {
            "product_id": data.get("sku") or data.get("mpn"),
            "product_name": name,
            "price": f"{price_val:.2f}",
            "currency": offers.get("priceCurrency") or self.currency,
            "category": None,
            "url": response.url,
            "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
        }
