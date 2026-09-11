"""
Spider for Beeyor (Dushanbe, Tajikistan restaurant food-delivery platform) —
https://beeyor.tj/.

A restaurant-delivery aggregator (per-dish menus), not a retail SKU catalog
— narrow COICOP 11.1.1 (restaurants/cafes). Server-rendered HTML, no auth.

The Russian-locale homepage (https://beeyor.tj/ru) card-links every
currently active Dushanbe restaurant at /ru/restaurant/detail/<slug>.
Confirmed 2026-09-10 by cross-checking all 24 cuisine-category pages
(/ru/restaurant/<cuisine>, e.g. /ru/restaurant/plov): none surfaced a
restaurant absent from the homepage's 46 -- the homepage IS the full
listing, there is no separate paginated "all restaurants" page. Each
restaurant detail page server-renders its full menu inline
(`.es-product-item` cards): ily-patio alone carries 222 dishes, romashka
85, czn-burak 145 -- far more than the 394-URL sitemap estimate that
motivated this source, because (see below) that sitemap is not even
beeyor.tj's own.

Price text is e.g. "40.00 cом" or, for variable-weight items, "от 4.00
cом" ("from 4.00 som") -- the regex pulls the first numeric token rather
than assuming it starts the string. Currency is the Tajik somoni (TJS);
the site prints the currency name ("сом"/"cом", inconsistent Cyrillic/Latin
"c"), never an ISO code, so TJS is set at the spider level per repo
convention (never derive currency from a displayed symbol/word).

Note: beeyor.tj's own /sitemap.xml is bogus -- every <loc> in it points at
cakelab.uz (an unrelated Uzbek cake shop; looks like a leftover from a
generic "Free Online Sitemap Generator" template never regenerated for
this domain). Do not use it for anything. This spider crawls outward from
the homepage instead, which is unaffected by the sitemap bug.

Page family: listing (homepage restaurant cards) + PDP-equivalent
(per-restaurant menu page, itself a listing of dishes).
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


class BeeyorTjSpider(scrapy.Spider):
    name = "beeyor_tj"
    allowed_domains = ["beeyor.tj"]
    start_urls = ["https://beeyor.tj/ru"]
    currency = "TJS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        seen = set()
        for href in response.css("a[href*='/restaurant/detail/']::attr(href)").getall():
            if href not in seen:
                seen.add(href)
                yield response.follow(href, callback=self.parse_restaurant)

    def parse_restaurant(self, response):
        restaurant_name = (response.css("h1::text").get(default="") or "").strip()
        for card in response.css(".es-product-item"):
            name = (card.css(".es-product-name::text").get(default="") or "").strip()
            price_text = (card.css(".es-current-price::text").get(default="") or "").strip()
            if not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price = m.group(1).replace(",", ".")
            try:
                if float(price) == 0:
                    continue
            except ValueError:
                continue
            yield {
                "product_id": card.attrib.get("data-id"),
                "product_name": name,
                "category": restaurant_name or None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.url,
                "language": self.language,
                "scraped_at_utc": response.headers.get("Date", b"").decode("utf-8", "ignore"),
            }
