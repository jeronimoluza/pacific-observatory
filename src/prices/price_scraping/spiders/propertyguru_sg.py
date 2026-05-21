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


class PropertyGuruSGSpider(scrapy.Spider):
    name = "propertyguru_sg"
    allowed_domains = ["www.propertyguru.com.sg"]
    currency = "SGD"
    language = "en"

    LANDING_URL = "https://www.propertyguru.com.sg/property-for-rent"
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

        return {
            "product_id": listing_id,
            "product_name": product_name[:500],
            "category": f"{prop_type}-for-rent",
            "price": str(rent_sgd),
            "currency": self.currency,
            "url": pdp_url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(
            "Request failed: %s — %r", failure.request.url, failure.value
        )
