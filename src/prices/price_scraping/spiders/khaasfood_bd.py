"""
Spider for Khaas Food (Bangladesh, specialty organic/halal food) -
https://www.khaasfood.com/

Tier 1A, but same trap as dmart_in: price/name are not in the DOM, they are
inside a React Server Component stream chunk
(`<script>self.__next_f.push([1,"..."])</script>`) with every quote
backslash-escaped on the wire. Category listing pages render with no price
data at all (client-fetched); PDPs embed a `"product":{...}` object with
salePrice/regularPrice. Full catalog enumerated via /sitemap.xml
(/product/<slug> entries).
"""

import logging
import re
from typing import Optional

import scrapy

logger = logging.getLogger(__name__)

_PRODUCT_RE = re.compile(
    r'"product":\{"id":"(?P<id>[^"]+)","name":"(?P<name>[^"]+)",'
    r'"variationName":"(?P<variation>[^"]*)","parentName":"[^"]*",'
    r'"slug":"[^"]*","salePrice":(?P<sale>[0-9.]+),'
    r'"regularPrice":(?P<regular>[0-9.]+)'
)


def _parse_product(unescaped_text: str) -> Optional[dict]:
    m = _PRODUCT_RE.search(unescaped_text)
    if not m:
        return None
    return m.groupdict()


class KhaasfoodBdSpider(scrapy.Spider):
    name = "khaasfood_bd"
    allowed_domains = ["khaasfood.com", "www.khaasfood.com"]
    currency = "BDT"

    async def start(self):
        yield scrapy.Request(
            "https://www.khaasfood.com/sitemap.xml",
            callback=self.parse_sitemap,
        )

    def parse_sitemap(self, response):
        locs = re.findall(r"<loc>(.*?)</loc>", response.text)
        product_urls = [loc for loc in locs if "/product/" in loc]
        logger.info(f"{self.name}: {len(product_urls)} product URLs in sitemap")
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        # Unescape the backslash-escaped RSC stream chunk (same trap as
        # dmart_in) before regex matching.
        text = response.text.replace('\\"', '"')
        data = _parse_product(text)
        if not data:
            logger.warning(f"Could not extract product data from {response.url}")
            return

        try:
            price_val = float(data["sale"])
        except (TypeError, ValueError):
            return
        if price_val <= 0:
            return

        name = data["name"].strip()
        variation = (data.get("variation") or "").strip()
        if variation:
            name = f"{name} ({variation})"

        yield {
            "product_id": data["id"],
            "product_name": name,
            "price": f"{price_val:.2f}",
            "currency": self.currency,
            "category": None,
            "url": response.url,
            "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
        }
