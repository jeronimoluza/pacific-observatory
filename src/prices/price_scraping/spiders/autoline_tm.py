"""
Autoline Turkmenistan — https://autoline-tm.com/.

Turkmenistan storefront of the Autoline used-vehicle classifieds
platform (same engine as autoline.info/autoline.ua and its many other
country domains). Category listing pages (e.g. /-/avtomobili--c1169 for
cars) server-render 25 cards per page with a real per-listing price in
Turkmen manat: `<span class="price-value has-tooltip" title="Цена">239
900 ТМТ</span>`. Pagination is a plain `?page=N`, verified to advance
(page 1 vs page 2 share zero listing IDs out of 25+25).

Some listings are auctions/"Аукцион" or negotiated ("Договорная") with no
fixed numeric price -- those carry the `price-value-negotiated` class
instead of a bare ruble/manat figure and are skipped (no price to record).

Category is the platform's own body-type tag (e.g. "Кроссовер",
"Седан"), not a COICOP-relevant grouping -- left as a free-text field
same as every other spider here.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://autoline-tm.com"
LISTING_URL = f"{BASE_URL}/-/avtomobili--c1169"
MAX_PAGES = 60  # ~1,500 listings; 8,118 total per the site's own count

_PRICE_RE = re.compile(r'title="Цена">\s*([\d\s]+)\s*ТМТ')
_CAT_RE = re.compile(r'class="cat-name">([^<]+)<')


class AutolineTmSpider(scrapy.Spider):
    name = "autoline_tm"
    allowed_domains = ["autoline-tm.com"]
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
        # Split into one chunk per listing card so price/category lookups
        # stay scoped to their own card instead of bleeding into the next.
        chunks = response.text.split('class="item sales-list-item')
        found = 0
        for chunk in chunks[1:]:
            code_m = re.search(r'data-code="(\d+)"', chunk)
            name_m = re.search(r'data-name="([^"]+)"', chunk)
            url_m = re.search(r'href="(https://autoline-tm\.com/-/[^"]+)"', chunk)
            price_m = _PRICE_RE.search(chunk)
            if not (code_m and name_m and url_m and price_m):
                continue  # auction/negotiated listing, or malformed card
            price = price_m.group(1).replace(" ", "").replace("\xa0", "")
            if not price.isdigit():
                continue
            cat_m = _CAT_RE.search(chunk)
            found += 1
            yield {
                "product_id": code_m.group(1),
                "product_name": name_m.group(1).strip()[:500],
                "category": cat_m.group(1).strip() if cat_m else None,
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
