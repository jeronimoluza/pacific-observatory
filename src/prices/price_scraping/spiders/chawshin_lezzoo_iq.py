"""
Spider for Chaw Shin Qasab ("qasab" = butcher) — a single, named, first-party
butcher/meat shop in Erbil, Iraq, whose storefront is hosted on Lezzoo
(www.lezzoo.com/erbil/m/chaw-shin-qasab-7108) rather than its own domain.
Same platform, pattern, and locality justification as bakhtiyari_lezzoo_iq —
see that spider's docstring for the Lezzoo/Restaurant-JSON-LD background.
This spider walks only this ONE named merchant's page, not Lezzoo's own
cross-merchant listing.

Verified live: 24 items, 0 blank names, 0 zero/negative prices, currency IQD
throughout, category composition 100% meat/butcher ("Meat", "Lamb Meat",
"Chicken", "Pickles", "Others" section names) -- channel=specialty-food.
"""

import json
import logging
import re

from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_VENUE_URL = "https://www.lezzoo.com/erbil/m/chaw-shin-qasab-7108"
_ID_RE = re.compile(r"-(\d+)$")


class ChawshinLezzooIqSpider(scrapy.Spider):
    name = "chawshin_lezzoo_iq"
    allowed_domains = ["lezzoo.com", "www.lezzoo.com"]
    currency = "IQD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _VENUE_URL, callback=self.parse_venue, errback=self.errback
        )

    def parse_venue(self, response):
        restaurant = self._extract_restaurant(response)
        if not restaurant:
            logger.warning(f"{self.name}: no Restaurant JSON-LD at {response.url}")
            return
        menu = restaurant.get("hasMenu") or {}
        sections = menu.get("hasMenuSection") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for section in sections:
            cat_name = section.get("name")
            for item in section.get("hasMenuItem") or []:
                name = item.get("name")
                offer = item.get("offers") or {}
                price = offer.get("price")
                url = item.get("url") or response.url
                if not name or price is None:
                    continue
                m = _ID_RE.search(url)
                product_id = m.group(1) if m else url
                n += 1
                yield {
                    "product_id": product_id,
                    "product_name": str(name).strip()[:500],
                    "category": cat_name,
                    "price": str(price),
                    "currency": offer.get("priceCurrency") or self.currency,
                    "available": "InStock" in str(offer.get("availability") or ""),
                    "url": url,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
        logger.info(f"{self.name}: {n} items from {len(sections)} sections")

    @staticmethod
    def _extract_restaurant(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Restaurant":
                    return c
        return None

    def errback(self, failure):
        logger.error(
            f"{self.name}: request failed {failure.request.url} — {failure.value!r}"
        )
