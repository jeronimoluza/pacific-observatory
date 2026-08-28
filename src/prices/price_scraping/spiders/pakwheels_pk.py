"""
Spider for PakWheels (www.pakwheels.com) -- used-car classifieds, Pakistan.

Server-rendered used-car search results; each `<li id="main_ad_...">`
listing embeds its own schema.org Product ld+json block directly (28 per
page, confirmed live), e.g.:
  <li id="main_ad_11873886" data-listing-id="11873886" ...>
    <script type="application/ld+json">
      {"@type": ["Product"], "name": "Honda Civic 2016 for sale in Lahore",
       "offers": {"@type": "Offer", "price": 4699000, "priceCurrency": "PKR",
                   "availability": "http://schema.org/InStock",
                   "url": "https://www.pakwheels.com/used-cars/..."}}

Pagination is `/used-cars/search/-/?page=N`; the site reports thousands of
pages (last-page link seen at page=3225), so this is capped well below that
to stay inside the collect-run time budget. All page requests are fanned
out from `start()` up front (bounded by MAX_PAGES) rather than chained one
page at a time, so CONCURRENT_REQUESTS_PER_DOMAIN actually parallelizes the
fetch instead of serializing it.

The catalog is overwhelmingly used cars — PakWheels is a single-vertical
vehicle marketplace, not a general classifieds site. The manifest declares
`coicop_codes: [07.1.1.2]` (second-hand motor cars) as a narrow source.

Re-verified live 2026-08-17: GET https://www.pakwheels.com/used-cars/search/-
-> 200, 28 ld+json Product blocks with real PKR prices (e.g. PKR 4,699,000
Honda Civic 2016).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.pakwheels.com"
# Site reports ~3225 pages of used-car listings; capped well below that to
# stay inside the ~25-minute collect-run budget (28 items/page). Bench
# 2026-08-17 (smoke): a single page fetch took ~2.2s. With pages now fanned
# out up front at CONCURRENT_REQUESTS_PER_DOMAIN=6, 250 pages is
# ~250/6*2.2s =~ 92s of fetch time in the best case, with real-world
# overhead/AUTOTHROTTLE backoff pushing that up -- comfortably inside the
# 25min budget even with a generous multiple of slack.
MAX_PAGES = 250

_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
    re.DOTALL,
)


class PakwheelsPkSpider(scrapy.Spider):
    name = "pakwheels_pk"
    allowed_domains = ["pakwheels.com"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 6,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/used-cars/search/-/",
            callback=self.parse_listing,
            meta={"page": 1},
        )
        for page in range(2, MAX_PAGES + 1):
            yield scrapy.Request(
                f"{_BASE}/used-cars/search/-/?page={page}",
                callback=self.parse_listing,
                meta={"page": page},
            )

    def parse_listing(self, response):
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if not isinstance(data, dict):
                continue
            types = data.get("@type")
            if types != "Product" and "Product" not in (types or []):
                continue
            offers = data.get("offers") or {}
            price = offers.get("price")
            name = data.get("name")
            url = offers.get("url")
            if not name or price in (None, "", 0) or not url:
                continue
            listing_id = url.rstrip("/").rsplit("-", 1)[-1]
            n += 1
            yield {
                "product_id": listing_id,
                "product_name": str(name).strip()[:500],
                "category": "used-cars",
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": str(offers.get("availability", "")).endswith("InStock"),
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: page={page} cards={n}")

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
