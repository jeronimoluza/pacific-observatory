"""
Naydizdes (Turkmenistan) — https://www.naydizdes.com/.

Osclass-based general classifieds site ("Free classifieds site #1 in
Turkmenistan"), hosted outside the country (147.135.215.129, unlike
almost every other Turkmen-registered domain probed for this country,
which sit on Turkmentelecom's own network and refuse external TCP
connections outright).

The real-estate section (/en/ashgabat/nedvijimost) server-renders up to
100 listing cards per page with a real per-listing price
(`<span class="item_price"> 4,500</span>`) and a category label in the
trailing `item_extra` line ("Flats and houses for rent", "Room for
rent", "Flats and houses for sale", ...). No currency symbol is printed
anywhere on the card or the item-detail page, but this is a
Turkmenistan-only site (no multi-country switch, no "$"-denominated
listings found in a full-page scan of either the rent or sale
subcategories) and several listing *descriptions* spell out "манат"
next to the same number shown in item_price (e.g. "Оплата 45[00
манат]" against item_price "4,500"), so prices are treated as TMT.
Pagination is `?page=N`; verified page=2 vs page=3 share only 1 of
101 items each (a pinned/VIP listing that always shows), i.e. it's a
genuine walk, not a re-served page.

Listings without a visible price ("price on request") have no
`item_price` span and are skipped, not filled with a placeholder.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.naydizdes.com"
LISTING_URL = f"{BASE_URL}/en/ashgabat/nedvijimost"
MAX_PAGES = 10  # ~779 listings total per the site's own item_count


class NaydizdesTmSpider(scrapy.Spider):
    name = "naydizdes_tm"
    allowed_domains = ["naydizdes.com"]
    currency = "TMT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{LISTING_URL}?page=1",
            callback=self.parse_page,
            meta={"page": 1},
            errback=self.errback,
        )

    def parse_page(self, response):
        page = response.meta["page"]
        chunks = response.text.split('<li class="item')
        found = 0
        for chunk in chunks[1:]:
            id_m = re.search(r'data-item="(\d+)"', chunk)
            url_m = re.search(
                r'href="(https://www\.naydizdes\.com/en/item/[^"]+)"', chunk
            )
            price_m = re.search(r'class="item_price">\s*([\d,]+)', chunk)
            title_m = re.search(r'class="item_title[^"]*">([^<]+)', chunk)
            extra_m = re.search(r'class="item_extra">([^<]+)', chunk)
            if not (id_m and url_m and price_m and title_m):
                continue  # "price on request" listing, or malformed card
            price = price_m.group(1).replace(",", "")
            # A handful of listings post a placeholder "1" (or similar tiny
            # figure) as an implicit "call for price" instead of leaving
            # item_price blank; no real Ashgabat property/rental posts for
            # under 100 TMT, so treat those as unpriced rather than real.
            if not price.isdigit() or int(price) < 100:
                continue
            category = None
            if extra_m:
                # "12 hours ago | Ashgabat | Flats and houses for rent | Rooms: 2 | Floor: 4"
                parts = [p.strip() for p in extra_m.group(1).split("|")]
                if len(parts) >= 3:
                    category = parts[2]
            found += 1
            yield {
                "product_id": id_m.group(1),
                "product_name": title_m.group(1).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url_m.group(1),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"{self.name}: page={page} priced_listings={found}")

        if found and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{LISTING_URL}?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
                errback=self.errback,
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
