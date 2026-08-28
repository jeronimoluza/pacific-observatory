"""
Spider for eBay UK (ebay.co.uk) — general marketplace.

Search results pages (/sch/i.html?_nkw=<kw>&LH_BIN=1&_ipg=240&_pgn=<n>) are
Marko-templated SSR HTML; each real listing sits in an
`<li class="s-card" ... data-listingid="<id>">` block with its own
`https://www.ebay.co.uk/itm/<id>?...` link. The very first "s-card" slot on
every page is a generic "Shop on eBay" promo card with a fake
`https://ebay.com/itm/123456` link and a USD placeholder price — excluded
by requiring the href to match the real `www.ebay.co.uk/itm/<id>` host.

LH_BIN=1 restricts results to fixed-price "Buy It Now" listings, excluding
live auctions — auction bid prices are not comparable shelf prices (per
onboarding brief). All prices under this filter, on ebay.co.uk, are GBP;
rows without a plain "£<amount>" price string are dropped rather than
guessed at.

The site's Human Security bot-check 403s a cookie-less request but sets
tracking cookies on that same 403 response that let the *next* request
through (confirmed live: request 1 -> 403 + Set-Cookie, request 2 with
those cookies -> 200). A throwaway priming request to the homepage runs
first so the real search requests (which share Scrapy's default
session-persistent cookiejar) land on an already-trusted session.
Confirmed live 2026-08-17.

Scoped to 12 keyword searches spanning electronics, apparel, furniture,
tools and hobby goods, 2 pages/keyword at _ipg=240 (~240 cards/page, ~240
with a real GBP price after filtering the promo slot) — a bounded basket,
not a full-catalog crawl.
"""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.ebay.co.uk"
PAGE_SIZE = 240
PAGES_PER_KEYWORD = 2

KEYWORDS = [
    "laptop",
    "smartphone",
    "headphones",
    "trainers",
    "jeans",
    "sofa",
    "bicycle",
    "power drill",
    "coffee machine",
    "vacuum cleaner",
    "camera",
    "watch",
]

_CARD_SPLIT_RE = re.compile(r'<li class="s-card')
_LISTINGID_RE = re.compile(r"data-listingid=(\d+)")
_HREF_RE = re.compile(r"href=(https://www\.ebay\.co\.uk/itm/\d+[^\s\"'>]*)")
_ALT_RE = re.compile(r'alt="([^"]*)"')
_PRICE_RE = re.compile(r'class="[^"]*s-card__price[^"]*"[^>]*>\s*£([\d,]+\.\d{2})')


class EbayUkSpider(scrapy.Spider):
    name = "ebay_uk"
    allowed_domains = ["ebay.co.uk", "www.ebay.co.uk"]
    currency = "GBP"
    language = "en"

    custom_settings = {
        "COOKIES_ENABLED": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [403, 500, 502, 503, 504, 522, 524, 408, 429],
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/",
            callback=self._dispatch_searches,
            errback=self._dispatch_searches,
            dont_filter=True,
        )

    def _dispatch_searches(self, _response_or_failure):
        for keyword in KEYWORDS:
            for page in range(1, PAGES_PER_KEYWORD + 1):
                yield scrapy.Request(
                    self._search_url(keyword, page),
                    callback=self.parse_search,
                    errback=self.errback,
                    meta={"keyword": keyword, "page": page},
                )

    @staticmethod
    def _search_url(keyword: str, page: int) -> str:
        return (
            f"{_BASE}/sch/i.html?_nkw={quote_plus(keyword)}&_sacat=0&LH_BIN=1"
            f"&_ipg={PAGE_SIZE}&_pgn={page}"
        )

    def parse_search(self, response):
        keyword = response.meta["keyword"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        starts = [m.start() for m in _CARD_SPLIT_RE.finditer(response.text)]
        starts.append(len(response.text))

        yielded = 0
        seen = set()
        for i in range(len(starts) - 1):
            card = response.text[starts[i] : starts[i + 1]]
            id_m = _LISTINGID_RE.search(card)
            href_m = _HREF_RE.search(card)
            alt_m = _ALT_RE.search(card)
            price_m = _PRICE_RE.search(card)
            if not (id_m and href_m and alt_m and price_m):
                continue
            listing_id = id_m.group(1)
            if listing_id in seen:
                continue
            seen.add(listing_id)

            name = html.unescape(alt_m.group(1)).strip()
            if not name:
                continue

            yield {
                "product_id": listing_id,
                "product_name": name[:500],
                "category": keyword,
                "price": price_m.group(1).replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": href_m.group(1),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1
        logger.info(f"ebay_uk: keyword={keyword} page={page} yielded={yielded}")

    def errback(self, failure):
        logger.error(
            f"ebay_uk request failed: {failure.request.url} — {failure.value!r}"
        )
