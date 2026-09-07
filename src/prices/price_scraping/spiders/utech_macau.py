"""UTech / Excel Macau Apple and computer catalog."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_BASE = "https://www.utechmacau.com/en/"
_START = f"{_BASE}product.php?cid=29"
_PRICE_RE = re.compile(r"[\d,.]+")
_PID_RE = re.compile(r"pid=(\d+)")


def _price(text: str | None) -> str | None:
    if not text:
        return None
    match = _PRICE_RE.search(text.replace(",", ""))
    return match.group(0) if match else None


class UtechMacauSpider(scrapy.Spider):
    name = "utech_macau"
    allowed_domains = ["www.utechmacau.com"]
    start_urls = [_START]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "USER_AGENT": "python-requests/2.32",
    }

    def parse(self, response):
        for card in response.css(".prd_item"):
            name = card.css(".prd_title::text").get()
            name = name.strip() if name else None
            price = _price(
                card.css(".prd_detail_sp_price::text").get()
                or card.css(".prd_price ::text").get()
            )
            href = card.css('.photo a[href*="product_detail"]::attr(href)').get()
            if not name or not price or not href:
                continue
            url = urljoin(response.url, href)
            pid_match = _PID_RE.search(url)
            yield {
                "product_id": pid_match.group(1) if pid_match else url,
                "product_name": name[:500],
                "category": "Electronics and computer devices",
                "price": price,
                "currency": "MOP",
                "available": True,
                "url": url,
                "language": "en",
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        next_href = response.css(".multipage a.next::attr(href)").get()
        if next_href:
            yield response.follow(next_href, callback=self.parse)
