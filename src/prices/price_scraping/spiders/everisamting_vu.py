"""
Spider for Everi Samting (Vanuatu classifieds) -- https://everisamting.com/

Self-described "#1 classified site" in Vanuatu. Server-rendered listing pages
under `/ads/<category-slug>?page=N` carry full listing cards (name, price,
location, category) with no need to fetch each PDP separately -- price is
already present in the listing card as `<span class="cards__price-title">`.

Discovered category slugs (19, from the homepage nav / footer, confirmed live
2026-09-06): agriculture, babies-and-kids, commercial-equipment-tools,
computers, education, electronics, fashion, handicrafts, health-beauty,
hobbies-sports-kids, home-furniture-appliances, home-living, jobs,
mobile-phones-tablets, pets-animals, property, services, sports-arts-and-
outdoors, vehicles.

NOTE: the sibling `/category/<slug>` route (no plural, singular "category")
that appears in some homepage links is BROKEN server-side -- it 500s with a
literal Laravel error page ("Method
App\\Http\\Controllers\\FilterController::adsByCategory does not exist").
Use `/ads/<slug>` (plural) exclusively; it returns 200 with real cards.

Pagination: `?page=N`, 1-indexed, ~15 cards/page. Stop condition is an empty
page (0 listing cards) -- confirmed vehicles has 8 populated pages, page 9
returns 0 `/ad/` links. No page-count is published anywhere, so this is a
walk-until-empty rather than a hardcoded range.

Card markup (verified 2026-09-06, `/ads/vehicles` sample):
  div.product_wrapper > div.product_item
    div.product_img > a[href=PDP] > img[alt=FULL title]
    div.product_content
      span.category_name -> display category text
      h2 > a[href=PDP] -> TRUNCATED title ("Used Toyota Land Cruiser...") --
        do not use this as product_name, prefer the img alt which carries
        the untruncated string.
      div.cards__info-bottom
        h3.cards__location[title=location string]
        span.cards__price-title -> "1,850,000 VT " (VUV, comma-grouped, "VT"
          suffix -- never parsed as the currency itself per rule 8; currency
          is hardcoded VUV from countries.yaml since Vanuatu has no other
          currency in circulation for this classifieds site).

product_id: no numeric ad ID is exposed anywhere in the card or PDP HTML
sampled; use the URL slug (last path segment) as a stable-enough identifier.

Wide category spread (vehicles, electronics, property, fashion, jobs,
services...) means coicop_classification=classifier, not source_curated --
same treatment as buynsellvanuatu_vu-class classifieds sites in the Vanuatu
inventory. "jobs" and "services" ads carry no product price in the retail
sense (job postings, service offers) -- these are naturally filtered out by
the price-parsing step below (no "VT" price on job/service cards in the
sampled pages, so rows without a parseable price are dropped rather than
special-cased per category).
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://everisamting.com"

_CATEGORIES = [
    "agriculture",
    "babies-and-kids",
    "commercial-equipment-tools",
    "computers",
    "education",
    "electronics",
    "fashion",
    "handicrafts",
    "health-beauty",
    "hobbies-sports-kids",
    "home-furniture-appliances",
    "home-living",
    "jobs",
    "mobile-phones-tablets",
    "pets-animals",
    "property",
    "services",
    "sports-arts-and-outdoors",
    "vehicles",
]

_PRICE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*VT", re.IGNORECASE)


class EverisamtingVuSpider(scrapy.Spider):
    name = "everisamting_vu"
    allowed_domains = ["everisamting.com"]
    currency = "VUV"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for category in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/ads/{category}",
                callback=self.parse_listing,
                cb_kwargs={"category": category, "page": 1},
            )

    def parse_listing(self, response, category, page):
        cards = response.css("div.product_wrapper")
        logger.info(
            f"everisamting_vu: category={category} page={page} found {len(cards)} cards"
        )
        if not cards:
            return

        for card in cards:
            href = card.css("div.product_img a::attr(href)").get()
            if not href:
                continue
            url = urljoin(_BASE, href)
            name = card.css("div.product_img img::attr(alt)").get()
            if not name:
                name = card.css("div.product_content h2 a::text").get()
            if not name:
                continue
            name = name.strip()

            price_text = card.css("span.cards__price-title::text").get()
            if not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            try:
                price = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue

            cat_name = card.css("span.category_name::text").get()
            product_id = url.rstrip("/").rsplit("/", 1)[-1]

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": (cat_name or category).strip(),
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        yield scrapy.Request(
            f"{_BASE}/ads/{category}?page={page + 1}",
            callback=self.parse_listing,
            cb_kwargs={"category": category, "page": page + 1},
        )
