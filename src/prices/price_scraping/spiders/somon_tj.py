"""somon.tj — Tajikistan classifieds marketplace (COICOP: mixed, marketplace).

Verified live 2026-08-17: top-level category listing pages (e.g.
``/elektronika-i-tehnika/``, ``/nedvizhimost/``, ``/transport/``) are
server-rendered with pagination via ``?page=<N>``. Two card layouts are used
depending on category default view:

- "card" layout (seen on ``/nedvizhimost/``, ``/transport/``): schema.org
  Offer microdata, ``meta[itemprop=price]``/``meta[itemprop=priceCurrency]``
  plus ``a.card__title-link`` for title+href.
- "advert-grid" layout (seen on ``/elektronika-i-tehnika/``,
  ``/odezhda-i-obuv/``, ``/kompyuteryi-i-orgtehnika/``, etc.): no microdata,
  price text lives in ``.advert-grid__content-price`` (a sibling of
  ``a.advert-grid__content-title`` under the same ``.advert-grid__content``
  container).

Both layouts are tried per page. Ad id + dedup key comes from the
``/adv/<id>_<slug>/`` URL. ``vakansii`` (job listings) and
``otdam-darom`` (giveaways, zero price) are excluded — not priced goods.
Category label comes from the page's ``<h1>`` (trimmed of the
" в Таджикистан" suffix the site appends to every category h1).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_AD_ID_RE = re.compile(r"/adv/(\d+)_")
_PRICE_NUM_RE = re.compile(r"[\d\s]+")
_H1_SUFFIX_RE = re.compile(r"\s+в\s+Таджикистан\s*$")

_CATEGORIES = (
    "nedvizhimost",
    "transport",
    "elektronika-i-tehnika",
    "telefonyi-i-svyaz",
    "detskij-mir",
    "hobbi",
    "biznes-i-uslugi",
    "stroitelstvo-syrye-i-remont",
    "vse-dlya-doma",
    "vsyo-dlya-biznesa",
    "zhivotnyie-i-rasteniya",
    "odezhda-i-obuv",
    "kompyuteryi-i-orgtehnika",
)


class SomonTjSpider(scrapy.Spider):
    name = "somon_tj"
    allowed_domains = ["somon.tj"]
    currency = "TJS"
    language = "tg"

    max_pages = 40

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.max_pages = int(kwargs.get("max_pages", self.max_pages))
        except (TypeError, ValueError):
            pass
        self.seen_ids: set[str] = set()

    async def start(self):
        for slug in _CATEGORIES:
            for page in range(1, self.max_pages + 1):
                yield scrapy.Request(
                    f"https://somon.tj/{slug}/?page={page}",
                    callback=self.parse_page,
                    meta={"page": page, "slug": slug},
                )

    def parse_page(self, response):
        category = self._category_label(response)
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0

        for a in response.css("a.card__title-link"):
            item = self._parse_card_layout(a, response, category, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        for a in response.css("a.advert-grid__content-title"):
            item = self._parse_grid_layout(a, response, category, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        logger.info(
            "slug=%s page=%s items=%d cumulative=%d",
            response.meta["slug"],
            response.meta["page"],
            emitted,
            len(self.seen_ids),
        )

    def _category_label(self, response) -> str | None:
        h1 = response.css("h1::text").get()
        if not h1:
            return None
        return _H1_SUFFIX_RE.sub("", h1.strip()).strip() or None

    def _ad_id(self, href: str | None) -> str | None:
        if not href:
            return None
        m = _AD_ID_RE.search(href)
        return m.group(1) if m else None

    def _parse_card_layout(self, a, response, category, scraped_at) -> dict | None:
        href = a.attrib.get("href")
        ad_id = self._ad_id(href)
        if not ad_id or ad_id in self.seen_ids:
            return None

        title = " ".join(t.strip() for t in a.css("::text").getall() if t.strip())
        if not title:
            return None

        span = a.xpath(
            "./preceding-sibling::span[contains(@class,'card__title-price')][1]"
        )
        price_content = span.css('meta[itemprop="price"]::attr(content)').get()
        currency = span.css('meta[itemprop="priceCurrency"]::attr(content)').get()
        price = self._normalize_price(price_content) if price_content else None
        if price is None:
            price_text = " ".join(span.css("::text").getall())
            price = self._normalize_price(price_text)
        if price is None:
            return None

        self.seen_ids.add(ad_id)
        return {
            "product_id": ad_id,
            "product_name": title[:500],
            "category": category,
            "price": price,
            "currency": currency or self.currency,
            "available": True,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def _parse_grid_layout(self, a, response, category, scraped_at) -> dict | None:
        href = a.attrib.get("href")
        ad_id = self._ad_id(href)
        if not ad_id or ad_id in self.seen_ids:
            return None

        title = (a.css("::text").get() or "").strip()
        if not title:
            return None

        container = a.xpath("parent::div[contains(@class,'advert-grid__content')]")
        price_text = " ".join(
            container.css(".advert-grid__content-price ::text").getall()
        )
        price = self._normalize_price(price_text)
        if price is None:
            return None

        self.seen_ids.add(ad_id)
        return {
            "product_id": ad_id,
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
    def _normalize_price(text: str) -> str | None:
        if not text:
            return None
        m = _PRICE_NUM_RE.search(text.replace("\xa0", " "))
        if not m:
            return None
        s = m.group(0).replace(" ", "").strip()
        if not s:
            return None
        try:
            float(s)
        except ValueError:
            return None
        return s
