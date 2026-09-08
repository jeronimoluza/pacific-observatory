"""
Spider for iMyanmarHouse -- https://www.imyanmarhouse.com/en/rent

Myanmar real-estate rental listings. The Myanmar discovery inventory
(2026-08-05) recorded this candidate BLOCKED (405 Method Not Allowed on
`/en/rent`) and deferred it in favour of ShweProperty/property.com.mm.
**Re-probed 2026-09-06: the site now returns a clean 200 with full,
server-rendered listing cards** -- the earlier block has cleared (whether
from a since-fixed server bug, a since-lifted block, or a transient issue
at the time of the original probe is not knowable in retrospect; the
current state is simply live and scrapeable). Confirms the onboarding
skill's "triage is often wrong, re-check before writing off" guidance in
the opposite direction from usual -- here a genuine former block cleared
naturally rather than needing a lever.

Card markup (`div[data-href^="/en/rent/"]`, verified live 2026-09-06):
  h2 > a[href=PDP] -> listing title (untruncated)
  p.fs-18.c-color.text-bold -> "100 Lakh (Kyats)" or "7,500 (US Dollar)"
    (comma-grouped numbers seen too, e.g. "1,000 lakhs") -- both currency
    forms present on the SAME listing page, same per-listing mix pattern
    as property_com_mm/ethiopiapropertycentre_et. Lakh = 100,000 units.
  p.main-theme-font-color (first of three) -> "Bahan | Yangon Region"
    (location, used loosely as category context, not a COICOP dimension)

No PDP fetch needed -- price and name are both on the listing card. Single
page, 20 listings confirmed live; no pagination parameter found in the
markup for this listing view (a future pass could investigate further).
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.imyanmarhouse.com"
_LISTING_URL = f"{_BASE}/en/rent"

_USD_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*\(US\s*Dollar\)", re.IGNORECASE)
_LAKH_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*Lakhs?\s*\(Kyats?\)", re.IGNORECASE)


class ImyanmarhouseMmSpider(scrapy.Spider):
    name = "imyanmarhouse_mm"
    allowed_domains = ["imyanmarhouse.com", "www.imyanmarhouse.com"]
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "DOWNLOAD_TIMEOUT": 45,
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
        cards = response.css('div[data-href^="/en/rent/"]')
        logger.info(f"imyanmarhouse_mm: found {len(cards)} listing cards")

        for card in cards:
            href = card.attrib.get("data-href")
            if not href:
                continue
            url = urljoin(_BASE, href)

            name = card.css("h2 a::text").get()
            if not name:
                continue
            name = name.strip()

            price_text = card.css("p.fs-18.c-color.text-bold::text").get()
            if not price_text:
                continue
            price_text = price_text.strip()

            currency = None
            price = None
            m_usd = _USD_RE.search(price_text)
            m_lakh = _LAKH_RE.search(price_text)
            if m_usd:
                currency = "USD"
                try:
                    price = float(m_usd.group(1).replace(",", ""))
                except ValueError:
                    pass
            elif m_lakh:
                currency = "MMK"
                try:
                    price = float(m_lakh.group(1).replace(",", "")) * 100_000
                except ValueError:
                    pass

            if price is None or currency is None or price <= 0:
                continue

            location_p = card.css("p.main-theme-font-color")[:1]
            location_parts = location_p.css("*::text").getall() if location_p else []
            category = (
                " ".join(p.strip() for p in location_parts if p.strip())
                or "Residential rental"
            )

            product_id = href.rstrip("/").rsplit("/", 1)[-1]

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
