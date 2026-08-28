"""reklama5.mk — North Macedonia classifieds marketplace (COICOP: mixed, marketplace).

Verified live 2026-08-17: ``/Search?pageView=1&page=<N>`` is a server-rendered
"all ads, newest first" feed across every category (~375k ads total at time of
writing). Cards: ``a.SearchAdTitle`` for title+href (``/AdDetails?ad=<id>``),
``span.search-ad-price`` for price text (``"11.990\\n €"`` — macedonian-locale
thousands separator is a dot), ``p.ad-category-div a`` for the category label.
No dedicated category-tree endpoint was found server-side (the left sidebar
menu is populated client-side), so this spider walks the mixed feed rather
than per-category listings.

Currency is NOT uniform: sellers price ads in either EUR ("€" suffix, the
majority) or MKD/denar ("МКД" suffix) — a live sample of 41 priced ads
showed 33 EUR + 8 MKD. Price parsing therefore reads the currency suffix per
row instead of assuming EUR sitewide. Ads priced "По Договор" (negotiable,
no digits) are dropped, same as any other unparseable price.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_AD_ID_RE = re.compile(r"[?&]ad=(\d+)")
_PRICE_NUM_RE = re.compile(r"[\d.,]+")


class Reklama5MkSpider(scrapy.Spider):
    name = "reklama5_mk"
    allowed_domains = ["reklama5.mk"]
    language = "mk"

    LANDING_URL = "https://www.reklama5.mk/Search?pageView=1"
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
        for page in range(1, self.max_pages + 1):
            yield scrapy.Request(
                f"{self.LANDING_URL}&page={page}",
                callback=self.parse_page,
                meta={"page": page},
            )

    def parse_page(self, response):
        cards = response.css("h3 a.SearchAdTitle")
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for card in cards:
            item = self._parse_card(card, response, scraped_at)
            if item is not None:
                yield item
                emitted += 1
        logger.info(
            "page=%s cards=%d items=%d cumulative=%d",
            response.meta["page"],
            len(cards),
            emitted,
            len(self.seen_ids),
        )

    def _parse_card(self, card, response, scraped_at: str) -> dict | None:
        href = card.attrib.get("href")
        if not href:
            return None
        m = _AD_ID_RE.search(href)
        if not m:
            return None
        ad_id = m.group(1)
        if ad_id in self.seen_ids:
            return None

        title = (card.css("::text").get() or "").strip()
        if not title:
            return None

        container = card.xpath("ancestor::div[contains(@class,'ad-desc-div')]")
        price_text = " ".join(container.css(".search-ad-price ::text").getall()).strip()
        parsed = self._parse_price(price_text)
        if parsed is None:
            return None
        price, currency = parsed

        category = (
            container.css(".ad-category-div a ::text").get() or ""
        ).strip() or None

        self.seen_ids.add(ad_id)
        return {
            "product_id": ad_id,
            "product_name": title[:500],
            "category": category,
            "price": price,
            "currency": currency,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _parse_price(text: str) -> tuple[str, str] | None:
        m = _PRICE_NUM_RE.search(text)
        if not m:
            return None
        s = m.group(0).replace(".", "").replace(",", ".")
        try:
            float(s)
        except ValueError:
            return None
        currency = "MKD" if "МКД" in text else "EUR"
        return s, currency
