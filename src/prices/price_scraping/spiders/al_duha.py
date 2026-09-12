"""
Al-Duha Bookstore / stationers (Syria) -- https://al-duha.com/
("مكتبة الضحى", Damascus -- al-Halbouni)

Custom Laravel storefront, server-rendered. No JSON API: the listing HTML
already carries everything needed, so this is a listing-only spider with
no PDP fetch.

MEASURED 2026-09-12 (curl_cffi impersonate=chrome124, no WAF):

    GET https://al-duha.com/products?page=N  -> 200, 15 distinct
    /product/<id> links per page. Pages 1, 2 and 3 returned disjoint
    id sets (zero overlap) -- genuine pagination.

LISTING MARKUP: one `<div class="product-card-wrap">` per product,
carrying `a[href="https://al-duha.com/product/<id>"]`,
`h6.product-card-title` (name) and `div.product-card-price >
span.price-current` (price).

CURRENCY: USD. The site's OWN price element renders "$6.00" and a
separate `div.price-syp` renders "≈ 840 ل.س" -- explicitly labelled an
approximation, and derived from an FX rate the site sets. We take the
site's primary quoted price (USD) and deliberately ignore the
approximate SYP conversion rather than emitting a derived number as an
observation.

CATALOG: stationery and school supplies (pens, notebooks, erasers,
rulers, colouring supplies) plus small household goods (tableware, tissue
boxes, small fans) and children's items. Spans COICOP 09.7 / 05.4 / 05.3,
so coicop_codes is left unset -- wide by the narrowness rule.

Page family: listing.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://al-duha.com"
MAX_PAGES = 40  # safety cap

_CARD_RE = re.compile(
    r'<a href="https://al-duha\.com/product/(\d+)" class="text-decoration-none">\s*'
    r'<h6 class="product-card-title">\s*(.*?)\s*</h6>.*?'
    r'<span class="price-current">\s*\$\s*([\d.,]+)\s*</span>',
    re.S,
)


class AlDuhaSpider(scrapy.Spider):
    name = "al_duha"
    allowed_domains = ["al-duha.com", "www.al-duha.com"]
    currency = "USD"
    language = "ar"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE}/products?page=1",
            callback=self.parse_listing,
            meta={"page": 1, "seen": set()},
        )

    def parse_listing(self, response):
        page = response.meta["page"]
        seen = response.meta["seen"]

        new_count = 0
        for pid, name, price_str in _CARD_RE.findall(response.text):
            if pid in seen:
                continue
            seen.add(pid)
            try:
                price = float(price_str.replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            new_count += 1
            yield {
                "product_id": pid,
                "product_name": re.sub(r"\s+", " ", name).strip()[:500],
                "category": None,
                "price": f"{price:.2f}",
                "currency": self.currency,
                "available": True,
                "url": f"{BASE}/product/{pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name} page={page} new={new_count} total_seen={len(seen)}")

        if new_count > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}/products?page={nxt}",
                callback=self.parse_listing,
                meta={"page": nxt, "seen": seen},
            )
