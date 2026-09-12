"""
Silver Store (Syria) -- https://silverstoreapp.com/

Broad-catalog Syrian online store (6Valley-style PHP storefront),
server-rendered. No JSON API found; the listing HTML carries name, PDP
link and price, so this is a listing-only spider with no PDP fetch.

MEASURED 2026-09-12 (curl_cffi impersonate=chrome124, no WAF):

    GET https://silverstoreapp.com/products?page=N -> 200, 20 product
    cards per page. Pages 1, 2 and 3 returned disjoint product-slug sets
    (zero overlap) -- genuine pagination.

LISTING MARKUP: one `div.product-single-hover` per product; the name and
PDP link live in `div.single-product-details h4 a[href=".../product/
<slug>"]` and the price in the following `h5.product-price span`
("700 ل.س").

CURRENCY: SYP, read from the page's own "ل.س" (Syrian Pound) suffix on
every price -- not inferred from the catalog or the TLD. No USD prices
were observed on the listing pages sampled.

CATALOG: genuinely wide -- the site's own category tree includes baby
food, automotive oils and fluids, bath and body, baby diapers, books
(aqidah, biography/memoir), bags, bar stools, amino acids, air
fresheners, action cameras and accessory sets, and its brand pages carry
Lipton, Ahmad Tea, Hamwi Cafe and Unicafe. Spans most of COICOP 01-13, so
coicop_codes is left unset and the classifier assigns the leaf per
product.

Page family: listing.
"""

import html as html_mod
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://silverstoreapp.com"
MAX_PAGES = 80  # safety cap

_CARD_RE = re.compile(
    r'<div class="single-product-details">.*?'
    r'<a href="https://silverstoreapp\.com/product/([^"]+)">\s*(.*?)\s*</a>.*?'
    r'<h5 class="product-price[^"]*">(.*?)</h5>',
    re.S,
)
_PRICE_RE = re.compile(r"([\d.,]+)\s*ل\.س")
_TAG_RE = re.compile(r"<[^>]+>")


class SilverstoreappSpider(scrapy.Spider):
    name = "silverstoreapp"
    allowed_domains = ["silverstoreapp.com", "www.silverstoreapp.com"]
    currency = "SYP"
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
        for slug, name_html, price_block in _CARD_RE.findall(response.text):
            if slug in seen:
                continue
            seen.add(slug)
            m = _PRICE_RE.search(price_block)
            if not m:
                continue
            try:
                price = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            name = html_mod.unescape(_TAG_RE.sub("", name_html))
            name = re.sub(r"\s+", " ", name).strip()
            if not name:
                continue
            new_count += 1
            yield {
                "product_id": slug,
                "product_name": name[:500],
                "category": None,
                "price": f"{price:.2f}",
                "currency": self.currency,
                "available": True,
                "url": f"{BASE}/product/{slug}",
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
