"""
Spider for Bakhtiyari Fruits and Vegetables World — a single, named,
first-party fresh-produce grocer in Erbil, Iraq, whose storefront is hosted
on Lezzoo (www.lezzoo.com/erbil/m/bakhtiyari-fruits-and-vegetables-world-855)
rather than its own domain. Lezzoo is "Kurdistan & Iraq's leading super app"
(food/groceries/pharmacy delivery, founded Erbil 2018, IQ address per its own
Organization JSON-LD) — this spider only walks ONE named merchant's page, not
Lezzoo's own cross-merchant listing, so the catalog scraped here is this one
grocer's, not a mixed marketplace catalog.

Next.js SSR: a plain GET (no special headers) embeds six
<script type="application/ld+json"> blocks; the fifth is a schema.org
"Restaurant" node (Lezzoo tags every venue type, including produce grocers,
as Restaurant) carrying hasMenu.hasMenuSection[].hasMenuItem[], each item
with its own unique PDP url + Offer{price, priceCurrency, availability}. One
GET returns the full first-page menu (28 sections / 60 items on this venue,
2026-08 sample) -- no further pagination is reachable via plain GET (same
known limitation as _wolt_base's page-1-only cap).

Verified live: 60 items, 0 blank names, 0 zero/negative prices, currency IQD
throughout, category composition 100% produce ("1 Kilo", "Box", "Fruits",
"Vegetables", "Herbs" section names only) -- channel=fresh-market.
"""

import json
import logging
import re

from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_VENUE_URL = "https://www.lezzoo.com/erbil/m/bakhtiyari-fruits-and-vegetables-world-855"
_ID_RE = re.compile(r"-(\d+)$")


class BakhtiyariLezzooIqSpider(scrapy.Spider):
    name = "bakhtiyari_lezzoo_iq"
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
