"""PropertyGuru MY — rental listings (COICOP 04.1.1).

Twin of ``propertyguru_sg``: identical SaaS frontend, identical card DOM
(``div.hui-card.listing-card-v2``). Only the locale-specific bits change
(currency MYR, PDP path ``/property-listing/...``, district path uses a
5-char alphanum suffix instead of the SG ``d<NN>`` district code).

Strategy: hit the rental landing, regex out the ~28 district paths
(``/property-for-rent/in-<area>-<5char>``), crawl each. ~20 cards per page.
"""

from __future__ import annotations

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


class PropertyGuruMYSpider(scrapy.Spider):
    name = "propertyguru_my"
    allowed_domains = ["www.propertyguru.com.my"]
    currency = "MYR"
    language = "en"

    LANDING_URL = "https://www.propertyguru.com.my/property-for-rent"
    IMPERSONATE_PROFILE = "chrome120"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_listing_ids: set[str] = set()
        self.discovered_districts: set[str] = set()

    def start_requests(self):
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
            item = self._parse_card(card, response.url, scraped_at)
            if item is None:
                continue
            yield item
            emitted += 1
        logger.info(
            "page=%s cards=%d items=%d cumulative=%d",
            page_label,
            len(cards),
            emitted,
            len(self.scraped_listing_ids),
        )

    def _parse_card(self, card, base_url: str, scraped_at: str) -> dict | None:
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

        return {
            "product_id": listing_id,
            "product_name": product_name[:500],
            "category": "for-rent",
            "price": str(rent),
            "currency": self.currency,
            "url": pdp_url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(
            "Request failed: %s — %r", failure.request.url, failure.value
        )
