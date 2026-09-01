"""PNGMart grocery category on PNG Business Directory."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_PRICE_RE = re.compile(r"PGK\s*([0-9]+(?:\.[0-9]+)?)", re.I)


class PngmartPgSpider(scrapy.Spider):
    name = "pngmart_pg"
    allowed_domains = ["pngbusinessdirectory.com", "www.pngbusinessdirectory.com"]
    start_urls = ["https://www.pngbusinessdirectory.com/mart/category/grocery/1"]
    currency = "PGK"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("div.col-xs-6.col-lg-3.m-top-5"):
            name = self._clean(card.css(".productName a::text").get())
            href = card.css(".productName a::attr(href)").get()
            text = self._clean(" ".join(card.xpath(".//text()").getall()))
            price_match = _PRICE_RE.search(text)
            if not name or not price_match:
                continue
            vendor = self._clean(card.css(".vendor a::text").get())
            brand = self._clean(card.css(".brand a::text").get())
            yield {
                "product_id": (href or name).rstrip("/").split("/")[-1],
                "product_name": name[:500],
                "category": "Grocery",
                "price": price_match.group(1),
                "currency": self.currency,
                "available": True,
                "brand": brand or None,
                "vendor": vendor or None,
                "url": href or response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        current = int(response.url.rstrip("/").rsplit("/", 1)[-1] or "1")
        if current >= 27:
            return
        next_url = (
            f"https://www.pngbusinessdirectory.com/mart/category/grocery/{current + 1}"
        )
        yield scrapy.Request(next_url, callback=self.parse)

    @staticmethod
    def _clean(value: str | None) -> str:
        return " ".join((value or "").split())
