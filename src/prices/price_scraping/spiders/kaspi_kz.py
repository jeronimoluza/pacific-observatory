"""kaspi.kz -- Kazakhstan's largest general marketplace, own commerce engine
(COICOP: mixed, marketplace/electronics-dominant).

The onboarding probe was right that the raw category HTML ships zero
product/price data (no JSON-LD Product markup at all, only Organization +
BreadcrumbList) -- this is a pure client-side app. A Playwright network
trace on a real category URl (pulled from the per-city sitemap) found the
actual listing JSON endpoint:

  GET https://kaspi.kz/yml/product-view/pl/filters
      ?q=:category:<Category Name>:availableInZones:<zone>&page=<N>
      &all=false&fl=true&ui=d&i=-1&c=<cityCode>
      Referer: https://kaspi.kz/shop/<city>/c/<url-encoded category>/

Verified live 2026-08-17 (Almaty, cityCode 750000000, zone 1): the SAME
request without a Referer header returns a plain nginx 403 (not a captcha,
not a JSON error) -- easy to mistake for a parse bug if the Referer is
missing. With the Referer set, it returns clean JSON:
  data.cards[] = {id, title, brand, unitPrice, unitSalePrice, priceFormatted,
                  currency, stock, category, ...}

Enumerability verified live: page=0 vs page=1 on category "Smart speakers"
returned 12 distinct card ids each, ZERO overlap (total: 351 for that
category alone).

Category coverage is a fixed list of leaf category names recovered live
from the Almaty per-city sitemap (https://kaspi.kz/shop/sitemap.xml ->
Category-ru-KZT-almaty.xml, 4,369 real leaf categories total; this spider
walks a curated sample, not the full taxonomy). The city id (750000000) and
zone (1) are pinned to Almaty for this smoke scaffold.

robots.txt sets ``Crawl-delay: 10`` -- respected via DOWNLOAD_DELAY=10 and a
matching AUTOTHROTTLE floor; RandomBrowserMiddleware's default chrome120
impersonation (project-wide, no override needed here) already clears the
page-load path, and this spider only needs curl_cffi for the API host,
which is the same host (kaspi.kz) as the page, so no extra allowed_domains
entry is required.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_CITY_CODE = "750000000"
_CITY_SLUG = "almaty"
_ZONE = "1"
_API_URL = "https://kaspi.kz/yml/product-view/pl/filters"

_CATEGORIES = (
    "smart speakers",
    "smartphones and gadgets",
    "vacuum cleaners",
    "microwave ovens",
    "tea kettles and samovars",
    "coffee grinders",
    "men shoes",
    "women shoes",
    "kitchen appliances",
    "toys",
    "headphones",
    "men fashion",
    "women fashion",
    "air conditioners",
)

MAX_PAGES = 5


class KaspiKzSpider(scrapy.Spider):
    name = "kaspi_kz"
    allowed_domains = ["kaspi.kz"]
    currency = "KZT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 10,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 10,
        "AUTOTHROTTLE_MAX_DELAY": 20,
    }

    async def start(self):
        for category in _CATEGORIES:
            yield self._page_request(category, 0)

    def _page_request(self, category: str, page: int):
        encoded_cat = quote(category)
        referer = f"https://kaspi.kz/shop/{_CITY_SLUG}/c/{encoded_cat}/"
        q = f":category:{category}:availableInZones:{_ZONE}"
        params = {
            "q": q,
            "page": str(page),
            "all": "false",
            "fl": "true",
            "ui": "d",
            "i": "-1",
            "c": _CITY_CODE,
        }
        query = "&".join(f"{k}={quote(v, safe='')}" for k, v in params.items())
        return scrapy.Request(
            f"{_API_URL}?{query}",
            callback=self.parse_page,
            headers={"Accept": "application/json", "Referer": referer},
            meta={"category": category, "page": page},
        )

    def parse_page(self, response):
        category = response.meta["category"]
        page = response.meta["page"]

        try:
            data = response.json()
        except ValueError:
            logger.warning(f"kaspi_kz: non-JSON response for {category} page={page}")
            return

        cards = (data.get("data") or {}).get("cards") or []
        logger.info(f"kaspi_kz: category={category} page={page} cards={len(cards)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            item = self._parse_card(card, category, scraped_at)
            if item is not None:
                yield item

        if cards and page < MAX_PAGES:
            yield self._page_request(category, page + 1)

    def _parse_card(self, card: dict, category: str, scraped_at: str) -> dict | None:
        card_id = card.get("id")
        name = card.get("title")
        price = card.get("unitSalePrice") or card.get("unitPrice")
        shop_link = card.get("shopLink")
        if card_id is None or not name or price is None or not shop_link:
            return None

        url = (
            shop_link
            if shop_link.startswith("http")
            else f"https://kaspi.kz{shop_link}"
        )

        return {
            "product_id": str(card_id),
            "product_name": str(name)[:500],
            "category": card.get("category") or category,
            "price": str(price),
            "currency": card.get("currency") or self.currency,
            "available": (card.get("stock") or 0) != 0 if "stock" in card else True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
