"""
Spider for Alliance Real Estate Vanuatu -- https://property.vu/

Residential rental listings for Port Vila and surrounds, built on the
OSProperty Joomla component. The Vanuatu discovery inventory (2026-08-05)
recorded this candidate at a now-404 URL
(`/vanuatu-rent-lease-listings/rent-vanuatu-residential`); the live path as
of 2026-09-06 is `/residential/for-rent`.

Single listing page, no pagination controls present -- 12 rental listings
confirmed live 2026-09-06, all with prices in the card itself (no PDP fetch
needed). This appears to be the entire current "for rent" catalog for this
small-market agency; re-check periodically in case listing volume grows
enough to paginate.

Card markup (per `<li class="col-md-6">` block):
  a.property_mark_a[href=PDP] > img[alt=full title]
  span.price -> "VT  290,000 /Per month" (VUV; "VT" + "/Per month" both
    parsed away, never used to derive the currency itself)
  p.property-ref-badge -> "AR335282" (stable per-listing reference code,
    used as product_id)
  h4 > a[title="Property details"] -> full listing title (redundant with
    img alt; used as fallback)

Scope: for-rent only, matching the onboarding skill's narrow-COICOP rule
(04.1.2 actual rentals). for-sale listings exist on the same site
(`/residential/for-sale`) but are a different COICOP concept (imputed
purchase, not a paid rental) and are out of scope here.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://property.vu"
_LISTING_URL = f"{_BASE}/residential/for-rent"

_PRICE_RE = re.compile(r"([\d,]+(?:\.\d+)?)")
_REF_RE = re.compile(r"(AR[0-9]+)")


class PropertyVuSpider(scrapy.Spider):
    name = "property_vu"
    allowed_domains = ["property.vu"]
    currency = "VUV"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_LISTING_URL, callback=self.parse_listing)

    def parse_listing(self, response):
        cards = response.css("li.col-md-6")
        logger.info(f"property_vu: found {len(cards)} listing cards")

        for card in cards:
            href = card.css("a.property_mark_a::attr(href)").get()
            if not href:
                continue
            url = urljoin(_BASE, href)

            name = card.css("a.property_mark_a img::attr(alt)").get()
            if not name:
                name = card.css('h4 a[title="Property details"]::text').get()
            if not name:
                continue
            name = name.strip()

            price_text = card.css("span.price::text").get()
            if not price_text:
                continue
            m = _PRICE_RE.search(price_text.replace(",", ""))
            if not m:
                continue
            try:
                price = float(m.group(1))
            except ValueError:
                continue
            if price <= 0:
                continue

            ref_text = card.css("p.property-ref-badge::text").get() or ""
            ref_m = _REF_RE.search(ref_text)
            product_id = ref_m.group(1) if ref_m else url.rstrip("/").rsplit("/", 1)[-1]

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Residential rental",
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
