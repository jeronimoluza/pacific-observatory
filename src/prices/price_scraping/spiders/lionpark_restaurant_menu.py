"""Lion Park Resort restaurant menu (Botswana)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"\bP\s*([0-9]+(?:\.[0-9]{1,2})?)\b", re.I)


class LionparkRestaurantMenuSpider(scrapy.Spider):
    name = "lionpark_restaurant_menu"
    allowed_domains = ["lionpark.co.bw", "www.lionpark.co.bw"]
    start_urls = ["https://www.lionpark.co.bw/restuarant-menu/"]
    currency = "BWP"
    language = "en"

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        # WordPress theme renders each menu entry as a list item. Keep the
        # nearest heading as category and ignore P... placeholder prices.
        category = "Restaurant menu"
        for node in response.xpath("//*[self::li or self::p]"):
            text = " ".join(node.xpath(".//text()").getall())
            text = " ".join(text.split())
            match = _PRICE_RE.search(text)
            if not match:
                continue
            name = text[: match.start()].strip(" -–—•:")
            if not name or len(name) > 500:
                continue
            yield {
                "product_id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:120],
                "product_name": name,
                "category": category,
                "price": match.group(1),
                "currency": self.currency,
                "available": True,
                "brand": None,
                "vendor": "Lion Park Resort Restaurant",
                "url": response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
