"""Trademaster Guam -- https://www.trademasterguam.com/.

Wix online store selling prepared Filipino dishes (adobo, afritada, chopsuey,
dinuguan, kaldereta, ...) in small consumer-sized portions (~$6-9 each; the
JSON-LD `seller.name` reads "New Fresh Bread", the underlying business name).
Wix has no public catalog JSON endpoint on this tenant, but every
/product-page/<slug> PDP server-renders a schema.org Product JSON-LD block
(name + Offers.price + Offers.priceCurrency) directly in the raw HTML -- no
Playwright needed. All ~29 products are linked from the homepage; ?page=2
returns the identical set (no further pagination to walk).
"""

import json
import logging
import re

from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)

_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)


class TrademasterGuamSpider(CrawlSpider):
    name = "trademasterguam"
    allowed_domains = ["trademasterguam.com", "www.trademasterguam.com"]
    start_urls = ["https://www.trademasterguam.com/"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    rules = (
        Rule(
            LinkExtractor(allow=r"/product-page/[^/?#]+$"),
            callback="parse_product",
            follow=False,
        ),
    )

    def parse_product(self, response):
        for block in _LD_JSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if data.get("@type") != "Product":
                continue
            offers = data.get("Offers") or data.get("offers") or {}
            price = offers.get("price")
            name = data.get("name")
            if not (name and price):
                continue
            yield {
                "product_id": response.url.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name.strip()[:500],
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "category": None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            return
        logger.warning("trademasterguam: no Product JSON-LD found at %s", response.url)
