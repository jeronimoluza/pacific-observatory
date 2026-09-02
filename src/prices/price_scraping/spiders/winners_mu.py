"""Winners (Mauritius, nopCommerce) — https://www.winners.mu/

General-merchandise supermarket chain with a full grocery range (BOUCHERIE,
BOULANGERIE, CHARCUTERIE, CREMERIE, EPICERIE, FRUITS ET LEGUMES,
POISSONNERIE, ...) alongside non-food departments (AUTO/VELO,
BRICO/MAISON/JARDIN, JOUETS, HYGIENE-BEAUTE, ELECTRO-MENAGER). Standard
nopCommerce storefront (`meta name="generator" content="nopCommerce"`),
server-rendered category pages -- Tier 1A, no Playwright needed. Re-verified
live 2026-09-01: HTTP 200, no WAF encountered on `curl_cffi impersonate=
chrome124` nor plain `requests`.

Category discovery: the homepage mega-menu marks true leaf categories with
`class="lastLevelCategory"` (268 confirmed 2026-09-01). Using this selector
instead of a raw href dump matters -- the homepage also carries a "featured
products" carousel whose links are single-segment slugs of the same shape
(e.g. /danesita-butter-cookies-454g), and would otherwise be miscounted as
categories.

Listing: `<category-slug>?pagesize=75&pagenumber=N` renders products
server-side in `div.product-item[data-productid]` blocks -- confirmed the
`pagesize` query param overrides the default 25/page UI dropdown (max UI
option is 75). Current price lives in `span.price.actual-price` ("Rs
979.90"); `span.price.old-price` (pre-discount) is intentionally not
captured, matching the convention in ramstore_do_doma_mk.py. A page is
followed to N+1 only while it returned a full PAGE_SIZE batch -- a
short/empty page is the last page for that category.

Price: "Rs" prefix, comma thousands separator on larger values (e.g. "Rs
1,979.90"), MUR's native 2-decimal subunit -- no minor-unit trap, the digits
are the price as displayed. Currency fixed at MUR (matches countries.yaml
and the storefront's own "Rs" display; no separate machine-readable currency
code was found to override it with).

Language: html lang="en" and product names skew English brand/product text
(LUMINARC MUG, MOULINEX TOASTER, COLD CHAIN RIB EYE) even though the
category taxonomy itself is French (BOUCHERIE, EPICERIE) -- matches
countries.yaml's first-listed language for Mauritius ([en, fr]).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.winners.mu"
PAGE_SIZE = 75
MAX_PAGES = 30  # safety cap per category (2,250 SKUs)

_LEAF_CATEGORY_RE = re.compile(
    r'class="lastLevelCategory" href="(?P<url>/[^"]+)" title="(?P<title>[^"]*)"'
)
_PRODUCT_RE = re.compile(
    r'<div class="product-item" data-productid="(?P<pid>\d+)">.*?'
    r'<h2 class="product-title"><a href="(?P<url>[^"]+)">(?P<name>[^<]+)</a></h2>.*?'
    r'<span class="price actual-price">\s*Rs\s*(?P<price>[\d,]+\.\d{2})\s*</span>',
    re.S,
)


def _clean_price(raw: str) -> str:
    return raw.replace(",", "")


class WinnersMuSpider(scrapy.Spider):
    name = "winners_mu"
    allowed_domains = ["winners.mu", "www.winners.mu"]
    currency = "MUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(f"{BASE_URL}/", callback=self.parse_home)

    def parse_home(self, response):
        leaves: dict[str, str] = {}
        for m in _LEAF_CATEGORY_RE.finditer(response.text):
            leaves[m.group("url")] = html.unescape(m.group("title")).strip()
        logger.info(f"{self.name}: {len(leaves)} leaf categories")
        for slug, title in leaves.items():
            yield scrapy.Request(
                response.urljoin(f"{slug}?pagesize={PAGE_SIZE}&pagenumber=1"),
                callback=self.parse_category,
                meta={"category": title, "page": 1, "base_slug": slug},
                dont_filter=True,
            )

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        base_slug = response.meta["base_slug"]
        matches = list(_PRODUCT_RE.finditer(response.text))
        logger.info(
            f"{self.name}: category={category} page={page} count={len(matches)}"
        )
        for m in matches:
            yield {
                "product_id": m.group("pid"),
                "product_name": html.unescape(m.group("name")).strip(),
                "category": category,
                "price": _clean_price(m.group("price")),
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(m.group("url")),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if len(matches) >= PAGE_SIZE and page < MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                response.urljoin(
                    f"{base_slug}?pagesize={PAGE_SIZE}&pagenumber={next_page}"
                ),
                callback=self.parse_category,
                meta={"category": category, "page": next_page, "base_slug": base_slug},
                dont_filter=True,
            )
