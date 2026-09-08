"""
Spider for 4321property.com -- Macao (Macau) rental listings.

4321 Property is a small international real-estate classifieds site
(4321property.com, with sibling country TLDs like 4321.co.il). Its Macao
section carries both "For Sale" and "For Rent" listings; this spider
scopes to RENT only (`Rental=rent`) -- COICOP 04.1.1 (actual rentals paid
by tenants), matching this repo's existing propertyguru_sg convention. Sale
listings are property-purchase transactions (investment, not household
consumption) and are intentionally out of scope.

Listing search results already embed everything needed inline -- price,
bedroom count, property type, city -- on
`https://www.4321property.com/search/?Rental=rent&Country=macau&page=N`,
so no PDP crawl is needed. Card markup is not selector-clean (heavy
inline-style/onclick duplication for mobile/desktop variants), so
extraction uses a regex window anchored on each card's `id="adid<ID>"`
marker rather than CSS selectors.

Pagination: `&page=N`, verified live 2026-09-06 -- Macao has exactly 3
pages (18 + 18 + 14 = 50 rental listings); page 4 302-redirects to a
DIFFERENT top-level site (4321.co.il, presumably the platform's Israel
country TLD reused when a country runs out of listings) rather than
returning an empty results page. `allowed_domains` guards against
following that redirect; the spider also stops once a page yields zero ad
ids.

Currency: MOP (Macanese Pataca) -- the site's own displayed currency for
Macao listings (confirmed inline: "MOP 19,000"), matches
countries.yaml's macao_sar_china entry.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.4321property.com/search/?Rental=rent&Country=macau&city=&search=&page={page}"
_MAX_PAGES = 20

_AD_ID_RE = re.compile(r'id="adid(\d+)"')
_PRICE_RE = re.compile(r"MOP\s*([\d,]+)")
_BEDS_TYPE_RE = re.compile(r"(\d+)\s*Bdrm\s*([A-Za-z /]+?)&nbsp;For Rent")
_CITY_RE = re.compile(r"cn=([^&\"']*)")


class Property4321MoSpider(scrapy.Spider):
    name = "4321property_mo"
    allowed_domains = ["4321property.com"]
    currency = "MOP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        yield scrapy.Request(_SEARCH_URL.format(page=1), cb_kwargs={"page": 1}, callback=self.parse_page)

    def parse_page(self, response, page):
        scraped_at = datetime.now(timezone.utc).isoformat()
        text = response.text
        ad_positions = [(m.group(1), m.start()) for m in _AD_ID_RE.finditer(text)]
        n = 0
        for ad_id, pos in ad_positions:
            window = text[pos : pos + 4000]
            price_m = _PRICE_RE.search(window)
            beds_m = _BEDS_TYPE_RE.search(window)
            city_m = _CITY_RE.search(window)
            if not price_m:
                continue
            try:
                price = float(price_m.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                # "Neg." (negotiable / price on request) listings render as
                # a literal "MOP 0" in the site's own markup -- not a
                # scraping artifact, but not a usable price either.
                continue
            beds = beds_m.group(1) if beds_m else None
            prop_type = beds_m.group(2).strip() if beds_m else None
            city = city_m.group(1) if city_m and city_m.group(1) else None
            category = f"{prop_type}, {beds} bedrooms" if prop_type else prop_type
            n += 1
            yield {
                "product_id": ad_id,
                "product_name": f"{prop_type or 'Property'} for rent"
                + (f", {city}" if city else ""),
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"https://www.4321property.com/macau/ad{ad_id}/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"{self.name}: {n} rows from page {page} ({len(ad_positions)} cards)")

        if n > 0 and page < _MAX_PAGES:
            yield scrapy.Request(
                _SEARCH_URL.format(page=page + 1),
                cb_kwargs={"page": page + 1},
                callback=self.parse_page,
            )
