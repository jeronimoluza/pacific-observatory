"""
Spider for Farmacias San Nicolas (El Salvador) -- https://www.farmaciasannicolas.com/.

Blazor Server-rendered storefront: each category page prerenders 20
product cards server-side (div.product-item), but the "Siguiente" /
numbered pagination controls are `href="javascript:;"` bound to a
SignalR circuit -- confirmed live 2026-08-17 that plain HTTP `?page=N`
on a category URL is a no-op (identical page 1 content), so only page 1
per category is reachable via Scrapy. The catalog is instead swept
broadly across ~190 leaf categories (scraped from the homepage nav,
`/category/<slug>/<code>`), which naturally bounds the crawl without
needing a page cap.

El Salvador is dollarized; prices render as "$29.03" -> USD, matching
countries.yaml.

Re-verified live 2026-08-17: GET /category/corazon-y-presion-arterial/
01003 -> 200, 287KB, 20 real product-item cards, e.g. "Ab-Life X 30
Capsulas" $25.84.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.farmaciasannicolas.com"
_CATEGORY_RE = re.compile(r'href="(/category/[a-z0-9\-]+/\d+)"')


class FarmaciasannicolasSvSpider(scrapy.Spider):
    name = "farmaciasannicolas_sv"
    allowed_domains = ["farmaciasannicolas.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(f"{_BASE}/", callback=self.parse_home)

    def parse_home(self, response):
        slugs = sorted(set(_CATEGORY_RE.findall(response.text)))
        logger.info(f"{self.name}: discovered {len(slugs)} categories")
        for slug in slugs:
            category = (
                slug.split("/category/", 1)[-1].rsplit("/", 1)[0].replace("-", " ")
            )
            yield scrapy.Request(
                urljoin(_BASE, slug),
                callback=self.parse_category,
                cb_kwargs={"category": category},
            )

    def parse_category(self, response, category):
        for card in response.css("div.product-item"):
            item = self._item(card, category)
            if item:
                yield item

    def _item(self, card, category):
        href = card.css("h3.prod-name a::attr(href)").get()
        name = card.css("h3.prod-name a::text").get()
        price = card.css("div.prices-top strong.price::text").get()
        if not href or not name or not price:
            return None
        price = re.sub(r"[^\d.]", "", price)
        if not price:
            return None
        return {
            "product_id": href.rstrip("/").rsplit("/", 1)[-1],
            "product_name": name.strip()[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(_BASE, href),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
