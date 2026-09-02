"""Spider for BIOMONDE Vata - https://biomonde.nc/vata/.

The site runs PrestaShop, but its theme omits the schema.org product marker
used by the shared PrestaShop base. Product cards on the landing page carry
stable PrestaShop ids, names, product URLs and visible FCFP prices.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import scrapy

_START_URL = "https://biomonde.nc/vata/"
_PRICE_RE = re.compile(r"\d[\d\s\u00a0\u202f.,]*")


def _clean(text: object) -> str:
    return re.sub(
        r"\s+",
        " ",
        html.unescape(str(text or "")).replace("\u00a0", " ").replace("\u202f", " "),
    ).strip()


class BiomondeNcSpider(scrapy.Spider):
    name = "biomonde_nc"
    allowed_domains = ["biomonde.nc"]
    currency = "XPF"
    language = "fr"

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
        for card in response.css("article.product-miniature"):
            product_id = _clean(card.attrib.get("data-id-product"))
            name = _clean(card.css(".product-title a::text").get())
            url = card.css(
                ".product-title a::attr(href), a.product-thumbnail::attr(href)"
            ).get()
            price = self._price(
                card.xpath('string(.//*[contains(@class, "price")])').get()
            )

            if not product_id or not name or price is None:
                continue

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": self._category(url),
                "price": price,
                "currency": self.currency,
                "available": "epuise"
                not in _clean(card.xpath("string(.)").get()).lower(),
                "url": url or response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _price(raw: object) -> str | None:
        match = _PRICE_RE.search(_clean(raw))
        if not match:
            return None
        value = match.group(0).replace(" ", "").replace(",", ".")
        try:
            parsed = float(value)
        except ValueError:
            return None
        if parsed <= 0:
            return None
        if parsed.is_integer():
            return str(int(parsed))
        return f"{parsed:.2f}"

    @staticmethod
    def _category(url: str | None) -> str | None:
        if not url:
            return None
        parts = [part for part in urlsplit(url).path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "vata":
            return parts[1].replace("-", " ")
        return None
