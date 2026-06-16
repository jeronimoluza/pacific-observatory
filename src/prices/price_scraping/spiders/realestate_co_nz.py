"""Spider for realestate.co.nz — residential rentals via JSON:API (Tier 1B)."""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://platform.realestate.co.nz/search/v1/listings"
PAGE_LIMIT = 50
SITE_BASE = "https://www.realestate.co.nz"

PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)")

REGION_FILTERS = [
    ("res_rent", None, "NZ Residential Rent"),
]


class RealestateCoNzSpider(scrapy.Spider):
    name = "realestate_co_nz"
    allowed_domains = ["platform.realestate.co.nz", "realestate.co.nz"]
    currency = "NZD"
    language = "en"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/vnd.api+json",
            "Accept-Language": "en-NZ,en;q=0.9",
            "Origin": SITE_BASE,
            "Referer": f"{SITE_BASE}/residential/rent",
        },
    }

    def _build_url(self, category, region_slug, offset):
        params = [
            ("filter[category][]", category),
            ("page[limit]", PAGE_LIMIT),
            ("page[offset]", offset),
        ]
        if region_slug:
            params.append(("filter[region-slug][]", region_slug))
        return f"{API_BASE}?{urlencode(params)}"

    async def start(self):
        for category, region_slug, label in REGION_FILTERS:
            url = self._build_url(category, region_slug, 0)
            yield scrapy.Request(
                url,
                callback=self.parse_api,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "category_label": label,
                    "category_filter": category,
                    "region_slug": region_slug,
                    "offset": 0,
                },
                errback=self.errback,
            )

    def parse_api(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(
                f"non-JSON response from {response.url}: {response.text[:200]}"
            )
            return

        if "data" not in payload:
            logger.warning(f"no data array at {response.url}: {response.text[:200]}")
            return

        records = payload.get("data") or []
        meta = payload.get("meta") or {}
        total = meta.get("totalResults") or 0
        offset = response.meta.get("offset", 0)
        category_label = response.meta.get("category_label")

        yielded = 0
        for rec in records:
            item = self._record_to_item(rec, category_label)
            if item:
                yield item
                yielded += 1

        logger.info(
            f"realestate_co_nz: {category_label} offset={offset} "
            f"records={len(records)} yielded={yielded} total={total}"
        )

        # paginate while there are more results and the page came back full
        next_offset = offset + PAGE_LIMIT
        if len(records) >= PAGE_LIMIT and next_offset < total:
            url = self._build_url(
                response.meta["category_filter"],
                response.meta.get("region_slug"),
                next_offset,
            )
            yield scrapy.Request(
                url,
                callback=self.parse_api,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "category_label": category_label,
                    "category_filter": response.meta["category_filter"],
                    "region_slug": response.meta.get("region_slug"),
                    "offset": next_offset,
                },
                errback=self.errback,
            )

    def _record_to_item(self, rec, category_label):
        rec_id = rec.get("id")
        attrs = rec.get("attributes") or {}
        if not rec_id or not attrs:
            return None

        price_display = attrs.get("price-display") or ""
        rent_amount = attrs.get("rent-in-advance-amount")

        price = None
        if rent_amount:
            try:
                if float(rent_amount) > 0:
                    price = str(rent_amount)
            except (TypeError, ValueError):
                pass
        if not price and price_display:
            m = PRICE_RE.search(price_display.replace(",", ""))
            if m:
                price = m.group(1)
        if not price:
            return None

        address = attrs.get("address") or {}
        display_addr = address.get("display-address") or address.get("full-address")
        suburb = address.get("suburb") or ""
        district = address.get("district") or ""
        region = address.get("region") or ""
        bedrooms = attrs.get("bedrooms") or attrs.get("bedroom-count")

        name_parts = []
        if display_addr:
            name_parts.append(display_addr)
        elif suburb or district:
            name_parts.append(", ".join(p for p in (suburb, district, region) if p))
        if bedrooms:
            name_parts.append(f"{bedrooms}br")
        product_name = " — ".join(name_parts) if name_parts else f"Listing {rec_id}"

        slug = attrs.get("website-slug")
        url = (
            f"{SITE_BASE}{slug}"
            if slug and slug.startswith("/")
            else (attrs.get("website-full-url") or f"{SITE_BASE}/property/{rec_id}")
        )

        available = bool(attrs.get("is-active", True)) and price_display != ""

        return {
            "product_id": str(rec_id),
            "product_name": product_name[:500],
            "category": category_label,
            "price": price,
            "currency": self.currency,
            "available": available,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
