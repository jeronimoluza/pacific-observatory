"""
Superseis — https://www.superseis.com.py/ (Asuncion-area full-line supermarket
chain, one of Paraguay's largest).

OpenCart-family storefront (`catalog/view/javascript/*` asset paths, classic
`price-new`/`price-normal` markup) served through clean SEO paths
(`/catalog/<top>/<sub>/<subsub>`) rather than the classic
`index.php?route=...&path=...` form, so `_opencart_base`'s two conventions
(numeric `path=` nav, or a hand-supplied `CATEGORY_URLS` list) don't fit --
this is a bespoke listing-card walker instead, same shape as spar_zw.

Product cards on category-listing pages carry `data-product-id` and
`data-product-price` directly on the `.product-thumb` div -- the *current*
(discounted, if any) selling price, verified against a live discounted item
(id 3135: `price-new` "37.000" / `price-old` "40.250" -> the div attribute
already reads "37.000") -- so listing pages are extracted directly with no
per-product page fetch needed.

Category tree is read once from the homepage's global nav menu (present in
every page's initial HTML, not just `/`): 546 category URLs, of which 430
are leaves (a leaf = a path that is not a strict prefix of another listed
path). Parent/ancestor category pages render only a curated subset of their
descendants' products, not the full set (verified: `/catalog/almacen` shows
15 cards vs. hundreds across its actual children) -- walking leaves only
avoids under- and double-counting. Each leaf is paged with `?page=N` until a
page returns zero product cards (verified: arroces has 24+12+0 across pages
1-3, a clean stop, not silent re-serving).

Currency PYG has no minor unit. `data-product-price` is formatted with `.`
as the thousands separator ("₲ 37.000" = 37000 PYG), never a decimal --
confirmed against countries.yaml and the brief's plausibility check (milk
~6,000-9,000 PYG/L).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.superseis.com.py"
CATEGORY_RE = re.compile(
    r'href="https://www\.superseis\.com\.py(/catalog/[a-z0-9/_-]+)"'
)


class SuperseisPySpider(scrapy.Spider):
    name = "superseis_py"
    allowed_domains = ["superseis.com.py"]
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
        yield scrapy.Request(
            f"{BASE_URL}/", callback=self.parse_nav, errback=self.errback
        )

    def parse_nav(self, response):
        paths = sorted(set(m.group(1) for m in CATEGORY_RE.finditer(response.text)))
        slugs = [p[len("/catalog/") :].strip("/") for p in paths]
        slug_set = set(slugs)
        leaves = [
            s
            for s in slugs
            if not any(o != s and o.startswith(s + "/") for o in slug_set)
        ]
        logger.info(f"{self.name}: {len(paths)} category urls, {len(leaves)} leaves")
        for slug in leaves:
            yield scrapy.Request(
                f"{BASE_URL}/catalog/{slug}?page=1",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": slug, "page": 1},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        cards = response.xpath('//div[contains(@class, "product-thumb")]')
        found = 0
        for card in cards:
            pid = card.attrib.get("data-product-id")
            raw_price = card.attrib.get("data-product-price") or ""
            name = card.css("a[data-product-name]::attr(data-product-name)").get()
            href = card.css("a[data-product-name]::attr(href)").get()
            if not pid or not name or not raw_price:
                continue
            digits = re.sub(r"[^\d]", "", raw_price)
            if not digits or int(digits) <= 0:
                continue
            found += 1
            yield {
                "product_id": pid,
                "product_name": name.strip()[:500],
                "category": category.replace("/", " > ").replace("-", " "),
                "price": digits,
                "currency": self.currency,
                "available": True,
                "url": href or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"{self.name}: {response.url} cards={len(cards)} yielded={found}")
        if cards:
            yield scrapy.Request(
                f"{BASE_URL}/catalog/{category}?page={page + 1}",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": category, "page": page + 1},
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
