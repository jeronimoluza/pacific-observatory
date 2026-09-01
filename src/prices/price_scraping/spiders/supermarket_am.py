"""supermarket.am — Supermarket.am (Armenia), Bitrix-based storefront.

Verified live 2026-09-01. Category list (269 leaves) scraped from the
homepage nav (``/categories/<slug>_<id>/``, no dedicated sitemap.xml — it
404s). The unprefixed root path (no ``/en/`` locale) serves Armenian
product names (e.g. "Պանիր հորած «Երեմյան Փրոդաքթս» 200գր"), same
Armenian-first preference as the sister site ``sas_am`` — the ``/en/``
sibling exists with identical ids/prices but translated names.

Product cards are ``div.td-overally`` (Bitrix component
``comp_<hash>``): name+PDP link at ``div.h3 a``, numeric id embedded in
both the href (``/products/_<id>/``) and the card's own
``id="bx_<component>_<id>"`` attribute, price in a hidden
``input.price`` field (e.g. ``"980 դր"`` on the Armenian path, ``"980
dr"``/``"1,250 dr"`` on ``/en/`` — comma OR space thousands separators
depending on path, both stripped by the digit-only regex).

Pagination is classic Bitrix ``?PAGEN_1=N`` and is **not
self-terminating**: requesting a page past the real last page (verified
live: page 4 on a 3-page/50-item category) silently wraps back to page 1's
content instead of an empty response — same trap as ``sas_am`` and
``parma_am``. The spider stops per-category once a page yields zero new
product ids, not on a short response.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_CAT_RE = re.compile(r'href="(/categories/[a-zA-Z0-9_-]+/)"')
_MAX_PAGES_PER_CATEGORY = 30


class SupermarketAmSpider(scrapy.Spider):
    name = "supermarket_am"
    allowed_domains = ["supermarket.am"]
    currency = "AMD"
    language = "hy"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request("https://supermarket.am/", callback=self.parse_home)

    def parse_home(self, response):
        paths = sorted(set(_CAT_RE.findall(response.text)))
        logger.info("supermarket_am: %d categories from homepage nav", len(paths))
        for path in paths:
            yield scrapy.Request(
                urljoin(response.url, path),
                callback=self.parse_category,
                meta={"path": path, "page": 1, "seen": set()},
            )

    def parse_category(self, response):
        path = response.meta["path"]
        page = response.meta["page"]
        seen: set = response.meta["seen"]

        cards = response.css("div.td-overally")
        title = response.css("div.intro h1::text").get()
        category = re.sub(r"\s+", " ", (title or "").strip()) or None

        scraped_at = datetime.now(timezone.utc).isoformat()
        ids_this_page = []
        for card in cards:
            item = self._parse_card(card, response, category, scraped_at)
            if item is None:
                continue
            ids_this_page.append(item["product_id"])
            if item["product_id"] in seen:
                continue
            yield item

        new_ids = set(ids_this_page) - seen
        logger.info(
            "supermarket_am: path=%s page=%s cards=%d new=%d",
            path,
            page,
            len(cards),
            len(new_ids),
        )

        if new_ids and page < _MAX_PAGES_PER_CATEGORY:
            seen = seen | new_ids
            next_page = page + 1
            yield scrapy.Request(
                urljoin(response.url, f"{path}?PAGEN_1={next_page}"),
                callback=self.parse_category,
                meta={"path": path, "page": next_page, "seen": seen},
            )

    def _parse_card(self, card, response, category, scraped_at: str) -> dict | None:
        a = card.css("div.h3 a")
        href = a.attrib.get("href")
        name = a.css("::text").get()
        price_raw = card.css("input.price::attr(value)").get()

        if not href or not name or not price_raw:
            return None

        m = re.search(r"_(\d+)/?$", href)
        if not m:
            return None
        product_id = m.group(1)

        digits = re.sub(r"[^\d]", "", price_raw)
        if not digits:
            return None

        name = re.sub(r"\s+", " ", name).strip()

        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": digits,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
