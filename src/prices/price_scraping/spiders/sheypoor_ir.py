"""
Spider for sheypoor.com — Iran classifieds marketplace.

Verified live 2026-08-17: SSR listing cards render inside a react-virtuoso
virtualized list at /s/tehran/<category>?page=N, ~26 cards/page, distinct
items confirmed across pages (page=1 vs page=2 ad-item ids disjoint). Each
card: `<a data-test-id="ad-item-<ID>" ... href="/v/<slug>-<ID>.html">`
containing an `<h2>` title and a price span (Persian digits) followed by a
sibling `data-test-id="icon-toman"` SVG, confirmed real listings e.g.
"کارتخوان سیار" (mobile card reader) at ۹,۰۰۰,۰۰۰ (9,000,000) Toman.

Prices on-site are quoted in Toman, not Rial (Iran's ISO 4217 currency).
1 Toman = 10 Rial, so the scraped Persian-digit price is multiplied by 10
here and reported as IRR, matching the site's own in-page "تومان"/toman
labelling while keeping the emitted currency ISO-valid.

Walks the 10 top-level Tehran category slugs from the homepage nav
(vehicles, real-estate, jobs, services, home, sports-games-hobbies,
electronics, industrial-commercial, mobile-tablet-accessories,
personal-stuff) with `?page=N` pagination, capped at MAX_PAGES/category.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.sheypoor.com"
_TOP_CATEGORIES = [
    "vehicles",
    "real-estate",
    "jobs",
    "services",
    "home",
    "sports-games-hobbies",
    "electronics",
    "industrial-commercial",
    "mobile-tablet-accessories",
    "personal-stuff",
]
MAX_PAGES = 60

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_CARD_RE = re.compile(r'data-test-id="ad-item-(\d+)"[^>]*href="([^"]+)"')
_TITLE_RE = re.compile(r"<h2[^>]*>([^<]+)</h2>")
_ICON_TOMAN_RE = re.compile(r'data-test-id="icon-toman"')
_PRICE_BEFORE_ICON_RE = re.compile(
    r">([۰-۹,]+)</span>\s*<span[^>]*>\s*(?:<!--\$-->)?\s*<svg[^>]*name=\"toman\""
)


class SheypoorIrSpider(scrapy.Spider):
    name = "sheypoor_ir"
    allowed_domains = ["sheypoor.com"]
    currency = "IRR"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/s/tehran/{slug}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        text = response.text

        matches = list(_CARD_RE.finditer(text))
        bounds = [m.start() for m in matches] + [len(text)]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for i, m in enumerate(matches):
            window = text[bounds[i] : bounds[i + 1]]
            title_m = _TITLE_RE.search(window)
            price_m = _PRICE_BEFORE_ICON_RE.search(window)
            if not (title_m and price_m):
                continue
            toman = int(price_m.group(1).translate(_PERSIAN_DIGITS).replace(",", ""))
            if toman <= 0:
                continue
            n += 1
            yield {
                "product_id": m.group(1),
                "product_name": title_m.group(1).strip()[:500],
                "category": slug,
                "price": str(toman * 10),
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, m.group(2)),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {slug} page={page} cards={n}")

        if page < MAX_PAGES and matches:
            yield scrapy.Request(
                f"{_BASE}/s/tehran/{slug}?page={page + 1}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": page + 1},
            )
