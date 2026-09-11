"""
Configurable spider for a single named-vendor storefront hosted on Lezzoo
(www.lezzoo.com/<city>/m/<vendor-slug>), reused across manifests instead of
one bespoke spider per vendor. Same platform/pattern/locality justification
as the earlier bakhtiyari_lezzoo_iq / chawshin_lezzoo_iq spiders — see those
for the original Lezzoo/JSON-LD discovery background.

Lezzoo's Next.js SSR embeds a schema.org JSON-LD node for the venue with
hasMenu.hasMenuSection[].hasMenuItem[], each item carrying its own PDP url
and Offer{price, priceCurrency, availability}. Observed both under
"@type": "Restaurant" (single-category venues, e.g. a butcher) and
"@type": "LocalBusiness" (multi-category "mart"-style venues) — this spider
accepts either, keying only on the presence of "hasMenu". A single GET
returns the full page-1 menu; no further pagination is reachable via plain
GET (same limitation already documented for the bespoke vendor spiders).
"""

import json
import logging
import re

from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"-(\d+)$")


class GenericLezzooVenueSpider(scrapy.Spider):
    name = "generic_lezzoo_venue"
    allowed_domains = ["lezzoo.com", "www.lezzoo.com"]
    currency = "IQD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def __init__(self, source_label=None, venue_url=None, currency=None, language="en", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if source_label:
            self.source_label = source_label
        self.venue_url = venue_url
        self.currency = currency or self.currency
        self.language = language or self.language

    async def start(self):
        yield scrapy.Request(
            self.venue_url, callback=self.parse_venue, errback=self.errback
        )

    def parse_venue(self, response):
        business = self._extract_business(response)
        if not business:
            logger.warning(f"{self.name}: no hasMenu JSON-LD at {response.url}")
            return
        menu = business.get("hasMenu") or {}
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
    def _extract_business(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for c in candidates:
                if isinstance(c, dict) and c.get("hasMenu"):
                    return c
        return None

    def errback(self, failure):
        logger.error(
            f"{self.name}: request failed {failure.request.url} — {failure.value!r}"
        )
