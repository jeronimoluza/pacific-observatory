"""Spider for Kemassa - https://kemassa.com/.

Kemassa is a small Addis Ababa farm-fresh produce storefront. Its landing
page is server-rendered and carries visible product cards with ETB prices.
Coverage is shallow, but the rows are clean fresh-food observations.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_BASE = "https://kemassa.com"
_START_URL = f"{_BASE}/"
_PRICE_RE = re.compile(r"([\d,.]+)\s*Br", re.I)
_UNIT_RE = re.compile(r"/\s*([A-Za-z]+)", re.I)


def _clean(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u00a0", " ")).strip()


class KemassaEtSpider(scrapy.Spider):
    name = "kemassa_et"
    allowed_domains = ["kemassa.com"]
    currency = "ETB"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_START_URL, callback=self.parse_home)

    def parse_home(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen: set[str] = set()

        for link in response.xpath("//a[starts-with(@href, '/products/')][.//h3]"):
            href = _clean(link.xpath("./@href").get())
            product_id = href.rsplit("/", 1)[-1] if href else ""
            name = _clean(" ".join(link.xpath(".//h3//text()").getall()))
            local_name = _clean(" ".join(link.xpath(".//p//text()").getall()))
            price_block = _clean(
                " ".join(link.xpath("following-sibling::div[1]//text()").getall())
            )
            prices = _PRICE_RE.findall(price_block)

            if not product_id or product_id in seen or not name or not prices:
                continue

            seen.add(product_id)
            unit_match = _UNIT_RE.search(price_block)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Fresh produce",
                "price": self._price(prices[-1]),
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
                "unit": unit_match.group(1).lower() if unit_match else None,
                "local_name": local_name or None,
            }

    @staticmethod
    def _price(raw: str) -> str:
        value = float(raw.replace(",", ""))
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
