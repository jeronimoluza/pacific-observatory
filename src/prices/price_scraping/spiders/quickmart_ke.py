"""
Quickmart Kenya — https://www.quickmart.co.ke/ (19-town online grocery, Q Soko).

Server-rendered PHP storefront (a "Growcer"-family multi-vendor grocery
template: `data-kit="F!GR"` in the homepage `<html>` tag). The catalogue is
location-gated -- every page loads a "No Quickmart branch found near your
delivery location" modal until a delivery point is set, matching the
triage GOTCHA. Verified live 2026-09-06 by reverse-engineering the site's
own jQuery bundle (`fcom.makeUrl('GeoLocation', 'setUpUserLocation')`):

  1. POST /geo-location/set-up-user-location with {lat, lng, address,
     radius (1-15)} -> sets a `_ygShopId` cookie (branch id) and a
     PHPSESSID for the rest of the crawl. No login needed. Picked a
     central Nairobi point (-1.286389, 36.817223) with radius=10, which
     resolves to the "Quickmart Tom Mboya" branch (shop_id=16) -- one
     town's worth of catalogue/pricing, not a national average (same
     accepted limitation as any single-branch scrape; the GOTCHA's
     "crawl per town" note is left for a future multi-branch pass).
  2. The 8 top-level category pages (foods, fresh, personal-care, liquor,
     homecare, households, electronics, textile -- found via POST
     /home/get-sidebar-category-menu) each aggregate their full
     subcategory tree (e.g. "foods" alone reports 3215 total records) and
     paginate with `?page-N` (a literal dash, NOT `?page=N` -- the `=`
     form silently re-serves page 1, a known trap shape; confirmed distinct
     product ids across page-1..page-6 on a sample category, empty page-7).

Product cards are server-rendered `div.products.productInfoJs` blocks with
name, PDP link, and price ("KES 62.00" -- always in whole-shilling display
format already matching the site's own currency, no minor-unit risk).
Category is the top-level nav slug (foods/fresh/etc.), not a fine-grained
COICOP-shaped label -- adequate since COICOP tagging happens downstream in
the classifier from product_name.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.quickmart.co.ke"
_TOP_CATEGORIES = [
    "foods",
    "fresh",
    "personal-care",
    "liquor",
    "homecare",
    "households",
    "electronics",
    "textile",
]
# Central Nairobi point; resolves to the "Quickmart Tom Mboya" branch.
_LAT, _LNG, _RADIUS = "-1.286389", "36.817223", "10"
_PRICE_RE = re.compile(r"([\d,]+\.\d{2})")


class QuickmartKeSpider(scrapy.Spider):
    name = "quickmart_ke"
    allowed_domains = ["quickmart.co.ke"]
    currency = "KES"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/",
            callback=self.parse_home,
            errback=self.errback,
        )

    def parse_home(self, response):
        body = f"lat={_LAT}&lng={_LNG}&address=Nairobi%2C+Kenya&radius={_RADIUS}"
        yield scrapy.Request(
            f"{BASE_URL}/geo-location/set-up-user-location",
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{BASE_URL}/",
            },
            body=body,
            callback=self.parse_geoloc,
            errback=self.errback,
        )

    def parse_geoloc(self, response):
        logger.info(f"{self.name}: geo-location response: {response.text[:200]}")
        for cat in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"{BASE_URL}/{cat}",
                callback=self.parse_listing,
                meta={"category": cat},
                errback=self.errback,
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        cards = response.css("div.products.productInfoJs")
        found = 0
        scraped_at = datetime.now(timezone.utc).isoformat()

        for card in cards:
            name = card.css("a.products-title::text").get()
            href = card.css("a.products-title::attr(href)").get()
            price_text = card.css(".products-price-new::text").get() or card.css(
                ".products-price span::text"
            ).get()
            form_class = card.css("form.addToCartForm::attr(class)").get() or ""

            if not name or not href or not price_text:
                continue

            price_match = _PRICE_RE.search(price_text)
            if not price_match:
                continue
            try:
                price_val = float(price_match.group(1).replace(",", ""))
            except ValueError:
                continue
            if price_val == 0:
                continue

            id_match = re.search(r"frmBuyProd-(\d+)", form_class)
            product_id = id_match.group(1) if id_match else href.rstrip("/").rsplit("-", 1)[-1]

            found += 1
            yield {
                "product_id": str(product_id),
                "product_name": name.strip()[:500],
                "category": category,
                "price": str(price_val),
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"{self.name}: {response.url} cards={len(cards)} yielded={found}")

        if cards:
            m = re.search(r"\?page-(\d+)$", response.url)
            next_page = int(m.group(1)) + 1 if m else 2
            yield scrapy.Request(
                f"{BASE_URL}/{category}?page-{next_page}",
                callback=self.parse_listing,
                meta={"category": category},
                errback=self.errback,
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
