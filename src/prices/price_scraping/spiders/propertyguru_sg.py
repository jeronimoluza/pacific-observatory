"""PropertyGuru SG — rental listings (COICOP 04.1.1).

Crack: TLS impersonation via curl_cffi `chrome120` (the project default profile).
The site previously returned a Cloudflare interactive challenge (`cf-mitigated:
challenge` + Turnstile) to bare requests; impersonate-chrome120 passes through
to a clean 200 + full SSR HTML. No Playwright required.

Crawl strategy: pagination is SPA-driven (`?page_num=N` is a no-op server-side
— every page-N anchor's href is the bare landing URL), so we widen coverage by
crawling per-district landing pages instead: ``/property-for-rent/in-<area>-d<NN>``.
~28 SG districts × ~20 listings/page ≈ 500–600 listings per scrape, with
geographic diversity that matters for COICOP 04.1.1 rent index purposes.

Per-card fields (rent, address, beds, sqft, psf) are inlined on the
``div.hui-card.listing-card-v2`` markup — no PDP crawl needed.

Template intent: reference build for EAP listing/Cloudflare-shielded spiders.
Cold Storage SG (groceries) and 99co-class real-estate sites can be cloned from
this file once their card DOMs are mapped.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"S\$\s*([\d,]+)\s*/mo", re.IGNORECASE)
_BEDS_RE = re.compile(r"(\d+)\s*(?:bed|bedroom|br)\b", re.IGNORECASE)
_SQFT_RE = re.compile(r"([\d,]+)\s*sqft", re.IGNORECASE)
_PSF_RE = re.compile(r"S\$\s*([\d.]+)\s*psf", re.IGNORECASE)
# Two URL forms: "/listing/hdb-for-rent-<addr>-<id>" and "/listing/for-rent-<name>-<id>"
# (HDB-public vs private/condo respectively).
_PDP_RE = re.compile(r"/listing/(?:([a-z]+)-)?for-rent-[a-z0-9-]+-(\d{6,})")
_DISTRICT_PATH_RE = re.compile(r"/property-for-rent/in-[a-z0-9-]+-d\d{1,2}\b")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class PropertyGuruSGSpider(scrapy.Spider):
    name = "propertyguru_sg"
    allowed_domains = ["www.propertyguru.com.sg"]
    currency = "SGD"
    language = "en"

    LANDING_URL = "https://www.propertyguru.com.sg/property-for-rent"
    IMPERSONATE_PROFILE = "chrome120"

    # PDP enrichment fetches each card's listing page to extract lat/lng from
    # __NEXT_DATA__.props.pageProps.pageData.data.listingLocationData.data.center.
    # Concurrency=3 is the bench-validated ceiling (2026-05-21: 50 PDPs/site
    # at c=3 ran clean across SG/MY/TH, zero CF challenges). 404/410 are
    # normal terminal responses for delisted PDPs — accept them so
    # parse_pdp can still emit the card-level item with lat=None.
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

    def start_requests(self):
        yield scrapy.Request(
            self.LANDING_URL,
            callback=self.parse_landing,
            meta={"impersonate": self.IMPERSONATE_PROFILE, "page_label": "landing"},
            errback=self.errback,
        )

    def parse_landing(self, response):
        yield from self._yield_cards(response, page_label="landing")

        # Districts live in inline JS/JSON blobs, not <a> anchors — regex the
        # raw body and dedupe.
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
            if "/listing/" in href:
                pdp_url = href if href.startswith("http") else urljoin(base_url, href)
                break
        if not pdp_url:
            return None

        m = _PDP_RE.search(pdp_url)
        if not m:
            return None
        prop_type = (m.group(1) or "private").lower()
        listing_id = m.group(2)
        if listing_id in self.scraped_listing_ids:
            return None
        self.scraped_listing_ids.add(listing_id)

        price_m = _PRICE_RE.search(html)
        if not price_m:
            return None
        rent_sgd = int(price_m.group(1).replace(",", ""))

        address = (card.css("h3::text").get() or "").strip() or None
        beds_m = _BEDS_RE.search(html)
        beds = beds_m.group(1) if beds_m else None
        sqft_m = _SQFT_RE.search(html)
        sqft = sqft_m.group(1).replace(",", "") if sqft_m else None
        psf_m = _PSF_RE.search(html)
        psf = psf_m.group(1) if psf_m else None

        name_parts = [
            prop_type.upper(),
            f"{beds}-bed" if beds else None,
            "rental",
            f"at {address}" if address else None,
            f"{sqft} sqft" if sqft else None,
            f"S$ {psf}/psf" if psf else None,
        ]
        product_name = ", ".join(p for p in name_parts if p)

        item = {
            "product_id": listing_id,
            "product_name": product_name[:500],
            "category": f"{prop_type}-for-rent",
            "price": str(rent_sgd),
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
    """Walk __NEXT_DATA__ to the listing center. A regex over the raw HTML
    is unsafe — PG PDPs embed school/MRT coords in the same JSON shape and
    a first-match regex can return the nearest MRT station instead of the
    listing (verified 2026-05-21 on SG listing 500145420)."""
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
    # PG renders center=null on listings that are mid-delisting; treat as
    # "no coord available" rather than an error.
    if not isinstance(center, dict):
        return None, None
    lat = center.get("lat")
    lng = center.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return float(lat), float(lng)
    return None, None
