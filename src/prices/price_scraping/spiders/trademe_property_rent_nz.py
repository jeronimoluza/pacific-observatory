"""Spider for trademe.co.nz — residential rental listings via JSON API (Tier 1B).

trademe.co.nz's Angular front-end renders search results client-side; the
listing data itself comes from a plain JSON endpoint
(api.trademe.co.nz/v1/search/property/rental.json) discovered via a
Playwright network trace on
https://www.trademe.co.nz/a/property/residential/rent/search. The endpoint
requires NO OAuth/API-key auth for this anonymous search call -- only a
client-generated `x-trademe-uniqueclientid` header (any UUID) and a
`Referer: https://www.trademe.co.nz/` header. (TradeMe's *formal* developer
API at the same host DOES require registered app credentials for most
endpoints -- confirmed 401 "supply your application credentials" when
calling without the two headers above; this specific search endpoint is the
public one the website itself uses and needs neither key nor OAuth.)

Verified live 2026-09-06: TotalCount ~11,900 NZ residential-rental listings;
page/page confirmed non-overlapping (page 1 vs page 2 = 0 shared ListingIds)
so the catalog genuinely paginates rather than being a fixed carousel.
"""

import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://api.trademe.co.nz/v1/search/property/rental.json"
SITE_BASE = "https://www.trademe.co.nz"
PAGE_ROWS = 50


class TrademePropertyRentNzSpider(scrapy.Spider):
    name = "trademe_property_rent_nz"
    allowed_domains = ["api.trademe.co.nz", "trademe.co.nz"]
    currency = "NZD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{SITE_BASE}/",
            "x-trademe-uniqueclientid": str(uuid.uuid4()),
        },
    }

    def _build_url(self, page):
        params = [
            ("rows", PAGE_ROWS),
            ("page", page),
            ("canonical_path", "/property/residential/rent"),
        ]
        return f"{API_BASE}?{urlencode(params)}"

    async def start(self):
        yield scrapy.Request(
            self._build_url(1),
            callback=self.parse_api,
            meta={"page": 1},
            errback=self.errback,
        )

    def parse_api(self, response):
        try:
            payload = response.json()
        except Exception:
            logger.warning(
                f"non-JSON response from {response.url}: {response.text[:200]}"
            )
            return

        records = payload.get("List") or []
        total = payload.get("TotalCount") or 0
        page = response.meta.get("page", 1)

        yielded = 0
        for rec in records:
            item = self._record_to_item(rec)
            if item:
                yield item
                yielded += 1

        logger.info(
            f"trademe_property_rent_nz: page={page} records={len(records)} "
            f"yielded={yielded} total={total}"
        )

        max_page = -(-total // PAGE_ROWS) if total else page  # ceil div
        if records and page < max_page:
            yield scrapy.Request(
                self._build_url(page + 1),
                callback=self.parse_api,
                meta={"page": page + 1},
                errback=self.errback,
            )

    def _record_to_item(self, rec):
        listing_id = rec.get("ListingId")
        rent_per_week = rec.get("RentPerWeek")
        if not listing_id or not rent_per_week:
            return None
        try:
            price = float(rent_per_week)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None

        address = rec.get("Address") or ""
        suburb = rec.get("Suburb") or ""
        district = rec.get("District") or ""
        region = rec.get("Region") or ""
        bedrooms = rec.get("Bedrooms")
        property_type = rec.get("PropertyType") or ""

        name_parts = [p for p in (address, suburb, district, region) if p]
        product_name = ", ".join(name_parts) if name_parts else f"Listing {listing_id}"
        if bedrooms:
            product_name = f"{product_name} — {bedrooms}br {property_type}".strip()

        url = f"{SITE_BASE}/a/property/residential/rent/listing/{listing_id}"

        return {
            "product_id": str(listing_id),
            "product_name": product_name[:500],
            "category": "NZ Residential Rent",
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
