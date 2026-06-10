"""Spider for Booking.com — Ukraine accommodation (Tier 2, Playwright).

Nightly hotel / apartment rates for the major Ukrainian cities, used as the
COICOP 11.2 (accommodation services) layer of the PPP basket. Booking only
surfaces a nightly price when a concrete date range is supplied, so we pin a
1-night stay ~30 days out for 2 adults and read the rendered ``UAH N`` price
off each property card.

Booking answers a generic curl with an HTTP 202 anti-bot stub; a real headless
Chromium clears it (the cards hydrate client-side), hence Playwright. Results
paginate via ``&offset=N`` (25 cards/page); we walk a couple of pages per city.
"""

import logging
import re
from datetime import date, timedelta
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

_BASE = "https://www.booking.com/searchresults.uk.html"

# Booking destination string (ss) per city -> stable English label.
CITIES = [
    ("Київ", "Kyiv"),
    ("Львів", "Lviv"),
    ("Одеса", "Odesa"),
    ("Харків", "Kharkiv"),
    ("Дніпро", "Dnipro"),
]

PAGES_PER_CITY = 2  # 25 cards/page
STAY_LEAD_DAYS = 30  # check-in this many days out (1-night stay)

# Booking renders prices like "UAH 2,000" (comma thousands), usually twice
# (struck original + final, identical). Collapse any thousands separator --
# comma or whitespace variant -- sitting *between* digits so "2,000" -> "2000",
# while the gap between two distinct prices is preserved.
_THOUSANDS_RE = re.compile(r"(?<=\d)[,\s\xa0\u202f\u2009\u200b]+(?=\d)")
_NUM_RE = re.compile(r"\d+")
_ID_RE = re.compile(r"/hotel/ua/([^.?/]+)")


class BookingUaSpider(scrapy.Spider):
    name = "booking_ua"
    allowed_domains = ["booking.com"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,
    }

    def _url(self, ss: str, offset: int, ci: str, co: str) -> str:
        from urllib.parse import urlencode

        q = {
            "ss": ss,
            "selected_currency": "UAH",
            "checkin": ci,
            "checkout": co,
            "group_adults": 2,
            "no_rooms": 1,
            "group_children": 0,
            "offset": offset,
        }
        return f"{_BASE}?{urlencode(q)}"

    def start_requests(self):
        ci = (date.today() + timedelta(days=STAY_LEAD_DAYS)).isoformat()
        co = (date.today() + timedelta(days=STAY_LEAD_DAYS + 1)).isoformat()
        for ss, label in CITIES:
            for page in range(PAGES_PER_CITY):
                url = self._url(ss, page * 25, ci, co)
                yield scrapy.Request(
                    url,
                    callback=self.parse_listing,
                    meta={
                        "playwright": True,
                        "playwright_page_goto_kwargs": {
                            "wait_until": "domcontentloaded"
                        },
                        "playwright_page_methods": [
                            PageMethod(
                                "wait_for_selector",
                                '[data-testid="property-card"]',
                                timeout=30000,
                            ),
                        ],
                        "city": label,
                        "stay": f"{ci}/{co}",
                    },
                    errback=self.errback,
                )

    def parse_listing(self, response):
        city = response.meta.get("city")
        stay = response.meta.get("stay")
        cards = response.css('[data-testid="property-card"]')
        logger.info("booking_ua: %s -> %d cards (%s)", city, len(cards), response.url)
        yielded = 0
        for c in cards:
            name = c.css('[data-testid="title"]::text').get()
            # The price is split across nested <span> text nodes ("UAH", "2",
            # "000"), so join all descendant text rather than taking one node.
            price_raw = " ".join(
                c.css('[data-testid="price-and-discounted-price"] ::text').getall()
            )
            href = c.css('a[data-testid="title-link"]::attr(href)').get()
            if not name or not price_raw or not href:
                continue
            # If a discount is shown the node holds [original, final]; the final
            # (actual) price is the last full number once thousands gaps close.
            collapsed = _THOUSANDS_RE.sub("", price_raw)
            matches = _NUM_RE.findall(collapsed)
            if not matches:
                continue
            price = matches[-1]
            sm = _ID_RE.search(href)
            yield {
                "product_id": sm.group(1) if sm else None,
                "product_name": name.strip()[:500],
                "price": price,
                "currency": self.currency,
                "category": f"Accommodation — {city} (1 night, 2 adults, {stay})",
                "url": response.urljoin(href.split("?")[0]),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info("booking_ua: yielded %d from %s", yielded, city)

    def errback(self, failure):
        logger.error("booking_ua request failed: %s — %r",
                     failure.request.url, failure.value)
