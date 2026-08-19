"""
Spider for Jumbo (Netherlands) — https://www.jumbo.com/.

Vue/Nuxt storefront. Category listing pages server-render the full product
grid: `data-testid="product-card-N" data-product-id="765935ZK"` marks each
card; within a card, `<a href="/producten/<slug>-<id>" class="title-link"
data-dd-action-name="NAME [Kompas ...">` gives the URL+name, and the
screen-reader price text `Prijs: €\xa03,75` (note: non-breaking space, not
a plain space, between the currency sign and the digits) gives the price.
Re-verified live 2026-08-06 via curl_cffi chrome impersonation: GET
/producten/zuivel,-boter-en-eieren/ -> 200, ~980KB SSR, 26 real product
cards incl. 'Scharreleieren 12 Stuks' EUR 3,75, 'Campina Vla Limited
Edition 1L' EUR 2,49. No WAF hit — overturns round 1's D-tier "SUSPECT"
call.

An earlier version of this spider used one long DOTALL regex spanning
data-product-id -> href -> alt -> price; that pattern silently matched
ZERO cards (the visible price is actually a whole/fractional span pair
for display styling, not plain text right after `data-testid="product-
price"`) while still costing several CPU-seconds per page from repeated
non-greedy backtracking. Fixed by splitting the page into per-card blocks
first (on the `product-card-N` marker), then running small anchored
regexes within each ~6KB block — both correct and fast.

Top-level category slugs are discovered from the /producten/ landing page's
own nav links (`/producten/<slug>/` with a trailing slash, no product-code
suffix — those are catalog-wide sections, e.g. `/producten/zuivel,-boter-
en-eieren/`, `/producten/aardappelen,-groente-en-fruit/`), each of which
paginates via `?offSet=N` (24 products/page observed on the site's own UI).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.jumbo.com"
_DISCOVERY_URL = f"{_BASE}/producten/"
_CATEGORY_RE = re.compile(r'href="(/producten/[^"?]+/)"')

_CARD_ID_RE = re.compile(r'data-testid="product-card-\d+" data-product-id="([^"]+)"')
_NAME_RE = re.compile(
    r'href="(/producten/[^"]+)" class="title-link"[^>]*data-dd-action-name="([^\[]+?) \[Kompas'
)
_PRICE_RE = re.compile(r"Prijs:\s*€\s*([0-9]+,[0-9]{2})")

MAX_PAGES = 50


class JumboNlSpider(scrapy.Spider):
    name = "jumbo_nl"
    allowed_domains = ["jumbo.com"]
    currency = "EUR"
    language = "nl"

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
        # RandomBrowserMiddleware rotates the curl_cffi impersonation profile
        # per request by default (chrome/firefox/safari/edge). Pin to Chrome
        # for consistency with the live probe.
        "IMPERSONATE_BROWSERS": ["chrome"],
    }

    async def start(self):
        yield scrapy.Request(_DISCOVERY_URL, callback=self.parse_discovery)

    def parse_discovery(self, response):
        cats = sorted(set(_CATEGORY_RE.findall(response.text)))
        logger.info(f"jumbo_nl: discovered {len(cats)} categories")
        for path in cats:
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_category,
                meta={"path": path, "offset": 0},
            )

    def parse_category(self, response):
        path = response.meta["path"]
        offset = response.meta["offset"]
        text = response.text
        positions = [m.start() for m in _CARD_ID_RE.finditer(text)]
        ids = _CARD_ID_RE.findall(text)
        logger.info(f"jumbo_nl: {path} offset={offset} count={len(positions)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        n_yielded = 0
        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(text)
            block = text[pos:end]
            name_match = _NAME_RE.search(block)
            price_match = _PRICE_RE.search(block)
            if not name_match or not price_match:
                continue
            url_path, name = name_match.groups()
            yield {
                "product_id": ids[i],
                "product_name": html.unescape(name).strip()[:500],
                "category": path.strip("/"),
                "price": price_match.group(1).replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            n_yielded += 1
        if n_yielded and offset // 24 < MAX_PAGES:
            nxt = offset + 24
            yield scrapy.Request(
                f"{_BASE}{path}?offSet={nxt}",
                callback=self.parse_category,
                meta={"path": path, "offset": nxt},
            )
