"""
Kilakitu (Burundi) — https://kilakitu.bi/.

General cross-division online store for Bujumbura, built on the Yo-Kart
multi-vendor marketplace platform (confirmed via /sitemap.xml, which still
points at the vendor's stale `v8.demo.yo-kart.com` demo sitemap — the real
site's own sitemap is broken, so this spider seeds from category listing
pages instead). Catalogue spans electronics, clothing, toys, cosmetics AND
a real food/beverage/alcohol range (14 categories below covering COICOP
01 and 02) — first retail source for Burundi (existing manifest is WFP
food-price averages only, `analytical_role: official_avg`).

Category listing pages are server-rendered Tier 1A HTML (confirmed live
2026-09-01, curl_cffi impersonate=chrome124, no Playwright needed).
Pagination is JS-triggered (`goToProductListingSearchPage(N)`) but the
underlying URL is a plain GET:
  https://kilakitu.bi/<slug>?sort-popularity-desc&pagesize-12&page-<N>
confirmed to return distinct products per page (sniffed via Playwright
network capture, then verified with curl_cffi alone).

Each product detail page carries a clean schema.org Product JSON-LD block
with name, price, priceCurrency (BIF), and canonical url. NOTE: the `sku`
field is a static "1" on every product observed (template bug on the
vendor's side) — do NOT use it as product_id. product_id is derived from
the canonical PDP URL slug instead.

Two vendor-side markup bugs found and fixed here (not ours to change
upstream): (1) the JSON-LD embeds a raw, unescaped newline inside the
"description" string on every product, which fails Python's default
strict JSON parsing and silently zeroed this spider on first run —
worked around with `json.loads(..., strict=False)`. (2) `<script>` is a
raw-text HTML element, so the page's own HTML entities (e.g. "&eacute;")
are never decoded by parsel's `::text` extraction the way normal markup
is — every accented French product name arrives HTML-escaped; worked
around with `html.unescape()`.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://kilakitu.bi"

# Food-and-beverage / alcohol category slugs only (COICOP 01/02) — the
# platform also sells electronics, clothing, toys, cosmetics, etc. which
# are out of scope for this sweep and would dilute the food share.
CATEGORY_SLUGS = [
    "food-items-190",
    "canned-jarred-packaged-foods-378",
    "candies-chocolates-202",
    "cookies-biscuits-199",
    "milk-tea-coffee-198",
    "nutrition-252",
    "quick-bites-379",
    "water-soft-drinks-juices-200",
    "beers-193",
    "gin-206",
    "red-wine-208",
    "vodka-194",
    "whiskey-207",
    "wines-spirits-192",
]

_MAX_PAGE_RE = re.compile(r"goToProductListingSearchPage\((\d+)\)")
_PAGE_SIZE = 12
_MAX_PAGES_HARD_CAP = 60  # safety valve; observed categories top out ~20


class KilakituBiSpider(scrapy.Spider):
    name = "kilakitu_bi"
    allowed_domains = ["kilakitu.bi"]
    currency = "BIF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in CATEGORY_SLUGS:
            yield scrapy.Request(
                f"{BASE_URL}/{slug}",
                callback=self.parse_category,
                errback=self.errback,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        product_urls = set(response.css("div.products__title a::attr(href)").getall())
        for href in product_urls:
            yield scrapy.Request(
                response.urljoin(href),
                callback=self.parse_product,
                errback=self.errback,
            )

        if page == 1:
            max_pages = [int(n) for n in _MAX_PAGE_RE.findall(response.text)]
            last_page = min(max(max_pages, default=1), _MAX_PAGES_HARD_CAP)
            logger.info(f"{self.name}: category={slug} last_page={last_page}")
            for n in range(2, last_page + 1):
                yield scrapy.Request(
                    f"{BASE_URL}/{slug}?sort-popularity-desc&pagesize-{_PAGE_SIZE}&page-{n}",
                    callback=self.parse_category,
                    errback=self.errback,
                    meta={"slug": slug, "page": n},
                )

    def parse_product(self, response):
        for script in response.css('script[type="application/ld+json"]::text').getall():
            try:
                # strict=False: this platform's Product JSON-LD embeds a raw,
                # unescaped newline inside the "description" string value
                # (confirmed live 2026-09-01 on every PDP sampled) — strict
                # JSON parsing raises "Invalid control character" on every
                # single product, silently zeroing the whole spider.
                data = json.loads(script, strict=False)
            except (json.JSONDecodeError, TypeError):
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    item = self._item(node, response.url)
                    if item:
                        yield item
                    return
        logger.warning(f"{self.name}: no Product JSON-LD at {response.url}")

    def _item(self, node: dict, url: str):
        name = node.get("name")
        offers = node.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        if not name or price is None:
            return None
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return None
        # A price of 0 is not an observation (confirmed live: a small number
        # of listings, e.g. the olive-oil SKUs, carry "0.00" for what is
        # presumably an out-of-stock/unpriced state) — drop, do not ship.
        if price_val <= 0:
            return None
        canonical_url = offers.get("url") or url
        return {
            "product_id": canonical_url.rstrip("/").rsplit("/", 1)[-1],
            # html.unescape: <script> is a raw-text element per HTML5, so the
            # page's own HTML entities (e.g. "&eacute;") are never decoded by
            # parsel's ::text extraction the way they would be in normal
            # markup — confirmed live 2026-09-01 (every accented product name
            # arrives HTML-escaped straight out of the JSON-LD blob).
            "product_name": html.unescape(str(name).strip())[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "outofstock"
            not in str(offers.get("availability") or "").lower(),
            "url": canonical_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
