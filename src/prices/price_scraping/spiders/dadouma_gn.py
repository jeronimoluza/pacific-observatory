"""Dadouma Guinea consumer marketplace catalog spider.

The server-rendered category tree starts at /categories/.  Top-level
``/categorie/`` pages enumerate leaf ``/produits/`` pages, and each leaf uses
stable ``a.dd-product-card`` markup for title, FG price, and canonical PDP URL.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.dadouma.com"
_PRODUCT_ID_RE = re.compile(r"/(\d{4,})/v-224(?:[/?#]|$)")
_PRICE_RE = re.compile(r"([\d\s\u00a0\u202f,.]+)\s*(?:FG|GNF)\b", re.IGNORECASE)


def _parse_price(text: str) -> str | None:
    match = _PRICE_RE.search(text or "")
    if not match:
        return None
    amount = re.sub(r"[\s\u00a0\u202f,]", "", match.group(1)).rstrip(".")
    return amount if amount.isdigit() and int(amount) > 0 else None


class DadoumaGnSpider(scrapy.Spider):
    name = "dadouma_gn"
    allowed_domains = ["dadouma.com", "www.dadouma.com"]
    currency = "GNF"
    language = "fr"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._request(f"{_BASE}/categories/", self.parse_categories)

    def _request(self, url: str, callback, **meta):
        return scrapy.Request(
            url,
            callback=callback,
            meta={"impersonate": "chrome124", **meta},
        )

    def parse_categories(self, response):
        urls = sorted(set(response.css('a[href*="/categorie/"]::attr(href)').getall()))
        logger.info("dadouma_gn: top_categories=%d", len(urls))
        for href in urls:
            yield self._request(response.urljoin(href), self.parse_category)

    def parse_category(self, response):
        leaf_urls = sorted(set(response.css('a[href*="/produits/"]::attr(href)').getall()))
        logger.info("dadouma_gn: category=%s leaves=%d", response.url, len(leaf_urls))
        for href in leaf_urls:
            yield self._request(response.urljoin(href), self.parse_leaf)

    def parse_leaf(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = (
            response.css("h1::text").get()
            or response.css("main h2::text").get()
            or response.url
        ).strip()
        cards = response.css("a.dd-product-card")
        yielded = 0

        for card in cards:
            href = card.attrib.get("href", "")
            id_match = _PRODUCT_ID_RE.search(href)
            name = (card.css("h3.dd-product-card__name::text").get() or "").strip()
            price_text = card.css("p.dd-product-card__price::text").get() or ""
            price = _parse_price(price_text)
            if not id_match or not name or not price:
                continue

            yielded += 1
            yield {
                "product_id": id_match.group(1),
                "product_name": name[:500],
                "category": category[:250],
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            "dadouma_gn: leaf=%s cards=%d yielded=%d",
            response.url,
            len(cards),
            yielded,
        )

