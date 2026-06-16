"""DDProperty TH — rental listings (COICOP 04.1.1).

DDProperty is PropertyGuru's Thailand brand. Identical SaaS frontend to
``propertyguru_sg`` / ``propertyguru_my``: same ``div.hui-card.listing-card-v2``
card DOM. Locale differences:

* Currency THB (``฿11,000 /mo``).
* PDP path is ``/en/property/<slug>-for-rent-<id>`` (not ``/listing/``).
* District path is ``/en/property-for-rent/in-<area>-th<NN>`` — ``th`` prefix
  with numeric region code (e.g. ``th10`` Bangkok, ``th50`` Chiang Mai).
* Site is English-localised under ``/en/``.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"฿\s*([\d,]+)\s*/mo", re.IGNORECASE)
_BEDS_RE = re.compile(r"(\d+)\s*(?:bed|bedroom|br)\b", re.IGNORECASE)
_SQM_RE = re.compile(r"([\d,]+)\s*(?:sq\s*m|sqm|m²)", re.IGNORECASE)
_PSQM_RE = re.compile(r"฿\s*([\d.,]+)\s*(?:/sqm|psqm|/m²)", re.IGNORECASE)
_PDP_RE = re.compile(r"/en/property/[a-z0-9-]+-for-rent-(\d{6,})")
_DISTRICT_PATH_RE = re.compile(r"/en/property-for-rent/in-[a-z0-9-]+-th\d{2,5}\b")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class DDPropertyTHSpider(scrapy.Spider):
    name = "ddproperty_th"
    allowed_domains = ["www.ddproperty.com"]
    currency = "THB"
    language = "en"

    LANDING_URL = "https://www.ddproperty.com/en/property-for-rent"
    IMPERSONATE_PROFILE = "chrome120"

    # See propertyguru_sg.py for the rationale. TH PDPs hit 100% coverage at
    # the c=3 bench (50/50 with valid coords), zero CF challenges.
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
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
            if "/en/property/" in href and "for-rent" in href:
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
        sqm_m = _SQM_RE.search(html)
        sqm = sqm_m.group(1).replace(",", "") if sqm_m else None
        psqm_m = _PSQM_RE.search(html)
        psqm = psqm_m.group(1) if psqm_m else None

        name_parts = [
            f"{beds}-bed" if beds else None,
            "rental",
            f"at {address}" if address else None,
            f"{sqm} sqm" if sqm else None,
            f"฿ {psqm}/sqm" if psqm else None,
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
