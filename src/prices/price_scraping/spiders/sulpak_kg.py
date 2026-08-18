"""sulpak.kg — Kyrgyz Republic electronics/appliances retailer.

Verified live 2026-08-17. The full category tree is not linked statically on
any page (the mega-menu is fetched client-side); it is however embedded as a
JSON-escaped HTML fragment returned by the site's own AJAX endpoint
``/Home/GetMainMenuView`` (found via ``data-mainMenuUrl`` on the homepage),
which yields ~470 ``/f/<slug>`` category paths. Category listing pages
(``https://www.sulpak.kg/f/<slug>``) are server-rendered with pagination via
``?page=<N>``; the current/total page count is printed as plain text
("Страница 1 из 32"), which this spider parses to bound the crawl per
category instead of guessing a fixed cap. Product cards are
``div.product__item-js``; name+id+url from ``div.product__item-name a``
(``data-product-id`` attr); current price (post-discount, not the
strikethrough ``.product__item-price-old``) from
``div.product__item-price``.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_MENU_URL = "https://www.sulpak.kg/Home/GetMainMenuView"
_CATEGORY_HREF_RE = re.compile(r'href="(/f/[^"]+)"')
_PRICE_NUM_RE = re.compile(r"[\d\s]+")
_TOTAL_PAGES_RE = re.compile(r"Страница\s*\d+\s*из\s*(\d+)")

_MAX_PAGES_PER_CATEGORY = 6


class SulpakKgSpider(scrapy.Spider):
    name = "sulpak_kg"
    allowed_domains = ["sulpak.kg", "www.sulpak.kg"]
    currency = "KGS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _MENU_URL,
            headers={"X-Requested-With": "XMLHttpRequest"},
            callback=self.parse_menu,
        )

    def parse_menu(self, response):
        try:
            raw_html = json.loads(response.text)
        except (ValueError, TypeError):
            raw_html = response.text

        slugs = set()
        for href in _CATEGORY_HREF_RE.findall(raw_html):
            slug = href.split("?")[0]
            if "%CITY%" in slug:
                continue
            slug = slug.rstrip("/")
            slugs.add(slug)

        logger.info("sulpak_kg: %d category paths discovered", len(slugs))
        for slug in sorted(slugs):
            yield scrapy.Request(
                f"https://www.sulpak.kg{slug}",
                callback=self.parse_category,
                meta={"page": 1, "slug": slug},
            )

    def parse_category(self, response):
        cards = response.css("div.product__item-js")
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = (response.css("h1::text").get() or "").strip() or None
        emitted = 0
        for card in cards:
            item = self._parse_card(card, response, category, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        page = response.meta["page"]
        slug = response.meta["slug"]
        logger.info(
            "sulpak_kg: slug=%s page=%s cards=%d items=%d",
            slug,
            page,
            len(cards),
            emitted,
        )

        if not cards:
            return
        total_pages = self._total_pages(response)
        max_page = min(total_pages, _MAX_PAGES_PER_CATEGORY)
        if page < max_page:
            nxt = page + 1
            yield scrapy.Request(
                f"https://www.sulpak.kg{slug}?page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "slug": slug},
            )

    @staticmethod
    def _total_pages(response) -> int:
        text = " ".join(response.css(".pagination__info ::text").getall())
        m = _TOTAL_PAGES_RE.search(text)
        return int(m.group(1)) if m else 1

    def _parse_card(self, card, response, category, scraped_at: str) -> dict | None:
        a = card.css("div.product__item-name a")
        product_id = a.attrib.get("data-product-id")
        href = a.attrib.get("href")
        title = " ".join(t.strip() for t in a.css("::text").getall() if t.strip())
        if not product_id or not href or not title:
            return None

        price = self._normalize_price(card.attrib.get("data-price"))
        if price is None:
            price_text = " ".join(card.css("div.product__item-price ::text").getall())
            price = self._normalize_price(price_text)
        if price is None:
            return None

        return {
            "product_id": product_id,
            "product_name": title[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _normalize_price(text: str | None) -> str | None:
        # data-price="0" is a real card state (item listed with no price set,
        # e.g. discontinued/on-request stock) rather than a parse failure —
        # treat it the same as "no price" and drop the row instead of
        # emitting a bogus 0.00.
        if not text:
            return None
        try:
            val = float(text)
            return str(val) if val > 0 else None
        except ValueError:
            pass
        m = _PRICE_NUM_RE.search(text.replace("\xa0", " "))
        if not m:
            return None
        s = m.group(0).replace(" ", "").strip()
        if not s:
            return None
        try:
            val = float(s)
        except ValueError:
            return None
        return s if val > 0 else None
