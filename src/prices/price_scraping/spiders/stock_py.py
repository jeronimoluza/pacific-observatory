"""
Stock — https://www.stock.com.py/ (Asuncion-area supermarket chain).

Same commercial group as Superseis (per the onboarding brief), but a
genuinely different storefront platform -- nopCommerce (ASP.NET WebForms,
`ctl00_ctl00_...` postback IDs, a literal `http://www.nopcommerce.com/`
footer credit link), not Superseis's OpenCart-family stack -- so this is not
a duplicate build, it is a second real backend.

Category URLs are flat and already leaf-level: `/category/<id>-<slug>.aspx`,
where the slug itself encodes the full category path
(`almacen-alimentos-secos-arroz`, not a generic `almacen`), so unlike
Superseis there is no parent/leaf tree to compute -- every category URL
found on the homepage nav is a leaf. 316 category URLs found there.

Each product card is a `<div class="product-item product<id>">`; name in
`a.product-title-link`, price in `span.price-label` (prefixed by a separate
`span.price-gs` "Gs" node -- the id/price/name selectors don't need it).
Every card also carries a `.producto-sin-existencia` placeholder div with a
broken-image icon regardless of real stock status (confirmed: present on
plainly-in-stock rice bags) -- it's a CSS/JS-toggled template slot, not a
live signal, so `available` is not derived from it and defaults to True.

Pagination is `?pageindex=N` (1-indexed, page 1 has no query string). It
mostly advances (distinct products on page 2 of a small category), but on
at least one category it stalled and re-served the same handful of items
past page 30 instead of ever returning zero cards -- so pagination stops on
"this page's card ids are all already-seen for this category" (a
per-category seen-id set), not on an empty-cards check alone, with a
MAX_PAGES safety cap as a second backstop.

Currency PYG, no minor unit: `price-label` text "  4.200" -> 4200 (dot =
thousands separator, same convention verified on Superseis).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.stock.com.py"
CATEGORY_RE = re.compile(
    r"https://www\.stock\.com\.py/category/(\d+-[a-z0-9\-]+)\.aspx"
)
CARD_ID_RE = re.compile(r"product-item product(\d+)")
MAX_PAGES_PER_CATEGORY = (
    100000  # dedup on new_ids: a re-served page gives new_ids=0 and stops
)


class StockPySpider(scrapy.Spider):
    name = "stock_py"
    allowed_domains = ["stock.com.py"]
    currency = "PYG"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        self.seen_by_category = {}
        yield scrapy.Request(
            f"{BASE_URL}/", callback=self.parse_nav, errback=self.errback
        )

    def parse_nav(self, response):
        slugs = sorted(set(CATEGORY_RE.findall(response.text)))
        logger.info(f"{self.name}: {len(slugs)} category urls")
        for slug in slugs:
            yield scrapy.Request(
                f"{BASE_URL}/category/{slug}.aspx",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": slug, "page": 1},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        seen = self.seen_by_category.setdefault(category, set())
        cards = response.xpath('//div[contains(@class, "product-item product")]')
        found = 0
        new_ids = 0
        for card in cards:
            cls = card.attrib.get("class", "")
            id_match = CARD_ID_RE.search(cls)
            pid = id_match.group(1) if id_match else None
            name = card.css("a.product-title-link::text").get()
            href = card.css("a.product-title-link::attr(href)").get()
            raw_price = card.css("span.price-label::text").get() or ""
            if not pid or not name or not raw_price:
                continue
            digits = re.sub(r"[^\d]", "", raw_price)
            if not digits or int(digits) <= 0:
                continue
            if pid not in seen:
                new_ids += 1
                seen.add(pid)
            found += 1
            yield {
                "product_id": pid,
                "product_name": name.strip()[:500],
                "category": category.split("-", 1)[-1].replace("-", " "),
                "price": digits,
                "currency": self.currency,
                "available": True,
                "url": href or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(
            f"{self.name}: {response.url} cards={len(cards)} yielded={found} new_ids={new_ids}"
        )
        # Stop when this page added no product ids not already seen for this
        # category (handles both a clean empty page and a stalled pager that
        # re-serves the same tail page forever), or at the safety cap.
        if cards and new_ids > 0 and page < MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                f"{BASE_URL}/category/{category}.aspx?pageindex={page + 1}",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": category, "page": page + 1},
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
