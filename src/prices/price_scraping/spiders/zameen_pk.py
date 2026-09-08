"""
Spider for Zameen.com (Pakistan — largest property marketplace) —
https://www.zameen.com/. Rental listings only (04.1.1 short-circuit) --
sale listings are excluded, same convention as mubawab_ma/avito_ma.

Server-rendered listing pages, no WAF -- curl_cffi chrome124 clears
/Rentals/<City>-<cityId>-<page>.html with a plain 200. Listing cards use
CSS-modules hashed class names (rebuild-fragile) but stable `aria-label`
attributes survive builds: `span[aria-label="Currency"]`,
`span[aria-label="Price"]`, `div[aria-label="Location"]`.

Re-verified live 2026-09-06: GET /Rentals/Lahore-1-1.html -> 200, 1.38MB,
25 `<li>` cards (the `/Property/<slug>-<id>-<id2>-1.html` anchor's `li[1]`
ancestor). Page 2 (`/Rentals/Lahore-1-2.html`) returns a disjoint 25-card
set (0 overlap) -- real pagination, confirmed. Sample: id 54539731's
sibling-page card 'Nawab Town, Lahore' 10-marla house PKR 1.25 Lakh/month.

Price unit suffix (Lakh=1e5, Thousand=1e3; Crore=1e7 appears on Homes/sale
pages, not Rentals, but handled anyway for safety) must be applied to the
leading numeric value -- "1.25 Lakh" is PKR 125000, not 1.25.

City list: only city ids verified live (Lahore=1, Karachi=2, Islamabad=3,
Faisalabad=15) are used; other guessed ids 404'd within probe budget.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.zameen.com"

_CITIES = [
    ("Lahore", 1),
    ("Karachi", 2),
    ("Islamabad", 3),
    ("Faisalabad", 15),
]

_MAX_PAGES_PER_CITY = 3
_ID_RE = re.compile(r"-(\d+)-\d+-\d+\.html$")
_UNIT_MULT = {
    "crore": 10_000_000,
    "lakh": 100_000,
    "thousand": 1_000,
}
_PRICE_RE = re.compile(r"([\d,.]+)\s*(Crore|Lakh|Thousand)?", re.I)


class ZameenPkSpider(scrapy.Spider):
    name = "zameen_pk"
    allowed_domains = ["zameen.com"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for city, city_id in _CITIES:
            yield scrapy.Request(
                f"{_BASE}/Rentals/{city}-{city_id}-1.html",
                callback=self.parse_listing,
                meta={"city": city, "city_id": city_id, "page": 1},
            )

    def parse_listing(self, response):
        city = response.meta["city"]
        city_id = response.meta["city_id"]
        page = response.meta["page"]
        cards = response.xpath('//a[starts-with(@href,"/Property/")]/ancestor::li[1]')
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for card in cards:
            item = self._item(card, city, response.url, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"zameen_pk: {city} page={page} items={n}")

        if cards and page < _MAX_PAGES_PER_CITY:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/Rentals/{city}-{city_id}-{next_page}.html",
                callback=self.parse_listing,
                meta={"city": city, "city_id": city_id, "page": next_page},
            )

    def _item(self, card, city: str, page_url: str, scraped_at: str):
        href = card.xpath('.//a[starts-with(@href,"/Property/")]/@href').get()
        title = card.xpath(".//div[@title]/@title").get()
        currency = card.xpath('.//span[@aria-label="Currency"]/text()').get()
        price_text = card.xpath('.//span[@aria-label="Price"]/text()').get()
        location = card.xpath('.//div[@aria-label="Location"]/text()').get()
        if not href or not title or not price_text:
            return None
        m = _ID_RE.search(href)
        listing_id = m.group(1) if m else href
        pm = _PRICE_RE.match(price_text.strip())
        if not pm:
            return None
        try:
            value = float(pm.group(1).replace(",", ""))
        except ValueError:
            return None
        unit = (pm.group(2) or "").lower()
        price = value * _UNIT_MULT.get(unit, 1)
        name = title.strip()
        if location:
            name = f"{name} ({location.strip()})"
        return {
            "product_id": str(listing_id),
            "product_name": name[:500],
            "category": "rental",
            "price": str(price),
            "currency": (currency or self.currency).strip(),
            "available": True,
            "url": urljoin(page_url, href),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
