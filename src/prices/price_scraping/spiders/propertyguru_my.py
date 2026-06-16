"""PropertyGuru MY — rental listings (COICOP 04.1.1).

Twin of ``propertyguru_sg``: identical SaaS frontend, identical card DOM
(``div.hui-card.listing-card-v2``). Only the locale-specific bits change
(currency MYR, PDP path ``/property-listing/...``, district path uses a
5-char alphanum suffix instead of the SG ``d<NN>`` district code).

Strategy: hit the rental landing, regex out the ~28 district paths
(``/property-for-rent/in-<area>-<5char>``), crawl each. ~20 cards per page.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"RM\s*([\d,]+)\s*/mo", re.IGNORECASE)
_BEDS_RE = re.compile(r"(\d+)\s*(?:bed|bedroom|br)\b", re.IGNORECASE)
_SQFT_RE = re.compile(r"([\d,]+)\s*sqft", re.IGNORECASE)
_PSF_RE = re.compile(r"RM\s*([\d.]+)\s*psf", re.IGNORECASE)
_PDP_RE = re.compile(r"/property-listing/[a-z0-9-]+-(\d{6,})")
_DISTRICT_PATH_RE = re.compile(r"/property-for-rent/in-[a-z0-9-]+-[a-z0-9]{5}\b")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class PropertyGuruMYSpider(scrapy.Spider):
    name = "propertyguru_my"
    allowed_domains = ["www.propertyguru.com.my"]
    currency = "MYR"
    language = "en"

    LANDING_URL = "https://www.propertyguru.com.my/property-for-rent"
    IMPERSONATE_PROFILE = "chrome120"

    # MY-specific: PG.com.my's CF holds the "blocked" state for longer than
    # SG/TH once it triggers. A 2026-05-21 run at CONCURRENT_REQUESTS_PER_DOMAIN=3
    # (the c=3 bench-validated value for SG/TH) had retry/max_reached=44 on MY
    # AND lost 126 card-listings to district-page 403s — the card crawl itself
    # got throttled, not just PDPs. SG at c=3 logged zero 403s; TH at c=3 had
    # 107 × 403 retries but ALL recovered within 3 attempts. MY needs serial
    # pacing. Each PDP takes ~600ms so the natural request rate at c=1 is
    # ~1.5/s — gentle enough that PG.com.my CF doesn't trip.
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 403],
        "HTTPERROR_ALLOWED_CODES": [404, 410],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_listing_ids: set[str] = set()
        self.discovered_districts: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            self.LANDING_URL,
            callback=self.parse_landing,
            meta={"impersonate": self.IMPERSONATE_PROFILE, "page_label": "landing"},
            errback=self.errback,
        )

    def parse_landing(self, response):
        yield from self._yield_cards(response, page_label="landing")

        district_paths = sorted(set(_DISTRICT_PATH_RE.findall(response.text)))
        self.discovered_districts.update(district_paths)
        logger.info("Discovered %d districts on landing", len(district_paths))

        for path in district_paths:
            yield scrapy.Request(
                urljoin(response.url, path),
                callback=self.parse_district,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "page_label": path},
                errback=self.errback,
            )

    def parse_district(self, response):
        yield from self._yield_cards(response, page_label=response.meta["page_label"])

    def _yield_cards(self, response, page_label: str):
        cards = response.css("div.hui-card.listing-card-v2")
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for card in cards:
            result = self._parse_card(card, response.url, scraped_at)
            if result is None:
                continue
            item, pdp_url = result
            yield scrapy.Request(
                pdp_url,
                callback=self.parse_pdp,
                errback=self.errback_pdp,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "item": item},
            )
            emitted += 1
        logger.info(
            "page=%s cards=%d items=%d cumulative=%d",
            page_label,
            len(cards),
            emitted,
            len(self.scraped_listing_ids),
        )

    def parse_pdp(self, response):
        item = response.meta["item"]
        item["pdp_status"] = response.status
        if response.status == 200:
            lat, lng = _extract_listing_center(response.text)
            item["lat"] = lat
            item["lng"] = lng
        yield item

    def errback_pdp(self, failure):
        item = failure.request.meta.get("item")
        logger.warning("PDP fetch failed: %s — %r", failure.request.url, failure.value)
        if item is not None:
            yield item

    def _parse_card(
        self, card, base_url: str, scraped_at: str
    ) -> tuple[dict, str] | None:
        html = card.get()

        pdp_url: str | None = None
        for href in card.css("a::attr(href)").getall():
            if "/property-listing/" in href:
                pdp_url = href if href.startswith("http") else urljoin(base_url, href)
                break
        if not pdp_url:
            return None

        m = _PDP_RE.search(pdp_url)
        if not m:
            return None
        listing_id = m.group(1)
        if listing_id in self.scraped_listing_ids:
            return None
        self.scraped_listing_ids.add(listing_id)

        price_m = _PRICE_RE.search(html)
        if not price_m:
            return None
        rent = int(price_m.group(1).replace(",", ""))

        address = (card.css("h3::text").get() or "").strip() or None
        beds_m = _BEDS_RE.search(html)
        beds = beds_m.group(1) if beds_m else None
        sqft_m = _SQFT_RE.search(html)
        sqft = sqft_m.group(1).replace(",", "") if sqft_m else None
        psf_m = _PSF_RE.search(html)
        psf = psf_m.group(1) if psf_m else None

        name_parts = [
            f"{beds}-bed" if beds else None,
            "rental",
            f"at {address}" if address else None,
            f"{sqft} sqft" if sqft else None,
            f"RM {psf}/psf" if psf else None,
        ]
        product_name = ", ".join(p for p in name_parts if p)

        item = {
            "product_id": listing_id,
            "product_name": product_name[:500],
            "category": "for-rent",
            "price": str(rent),
            "currency": self.currency,
            "url": pdp_url,
            "language": self.language,
            "lat": None,
            "lng": None,
            "pdp_status": None,
            "scraped_at_utc": scraped_at,
        }
        return item, pdp_url

    def errback(self, failure):
        logger.error("Request failed: %s — %r", failure.request.url, failure.value)


def _extract_listing_center(html: str) -> tuple[float | None, float | None]:
    """Walk __NEXT_DATA__ to the listing center. See propertyguru_sg.py for
    why a raw-HTML regex is unsafe (MRT/landmark coord collisions)."""
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None, None
    try:
        blob = json.loads(m.group(1))
        center = blob["props"]["pageProps"]["pageData"]["data"]["listingLocationData"][
            "data"
        ]["center"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return None, None
    if not isinstance(center, dict):
        return None, None
    lat = center.get("lat")
    lng = center.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return float(lat), float(lng)
    return None, None
