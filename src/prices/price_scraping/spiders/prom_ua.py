"""Prom.ua -- Ukraine's largest general marketplace -- https://prom.ua/
(COICOP: mixed, marketplace).

Verified live 2026-09-10: curl_cffi impersonate=chrome124 clears cleanly
(no WAF challenge observed on category pages).

**Deviates from the wave-3 addendum's GraphQL suggestion -- documented
here so the next person doesn't repeat the investigation.** A Playwright
network trace of ``POST https://prom.ua/graphql`` shows only widget
queries (``AnalyticsQuery``, ``BesidaDataQuery``, ``AutocompleteSearchQuery``,
``PersonalFeedBlockQuery`` (a personalization feed keyed by client id, not
a category listing), ``CompareProductsQuery``, ``PromoLabelsQuery``). The
one category-scoped query, ``CategoryFiltersQuery`` -> ``categoryListing``,
only returns the ``filters`` sub-object (facet counts, a ``total`` sentinel
capped at 10000) -- it has no ``products`` field the client ever requests.
The real catalog is server-rendered HTML: ``GET /ua/<CategoryAlias>``
embeds product tiles directly (``data-qaid="qa_product_tile"`` with a
``data-product-id`` attribute; name in
``a[data-qaid="product_link"] span``; price as a clean numeric attribute
``div[data-qaid="product_price"]::attr(data-qaprice)``, currency symbol in
``::attr(data-qacurrency)`` -- always UAH hryvnia (`₴`) on this TLD).
So this ships as ``scrapy_html`` (Tier 1A), not ``scrapy_api``.

Pagination is a semicolon path segment, not a query string --
``https://prom.ua/ua/<Alias>;<N>`` (``?page=N`` has NO effect; confirmed
identical output for N=1/2/3 -- the site's own pagination widget renders
plain ``<a href="...;2">2</a>`` links, not JS-fetched pages).

Enumerability, live-verified on ``Chehly-dlya-telefonov`` (phone cases,
one of the larger categories): page 1 vs page 2 overlap 10/20 ids, page 2
vs page 3 overlap 10/20 -- roughly half of each page is new. The
persistent ~50% overlap is sponsored/advertised listings (`Prosale`
adverts) that repeat near the top of every page; the other half is
genuine, changing catalog depth. This is DISTINCT, not the same-page-
forever failure mode -- confirmed against a thin category too
(``Kofe``, coffee) where overlap across 3 pages was much higher (near-
total), consistent with that alias just having a small real assortment
behind an inflated "8000+" total-count badge. Categories vary a lot in
real depth; this spider does not try to detect that automatically and
just walks a fixed page cap per category.

25 real category aliases were harvested from the rendered homepage nav
(2026-09-10); this spider uses a diverse 15-category subset (electronics,
fashion, home, pets, auto, beauty, kids, sport) -- a general-marketplace
catalog, not food-led.

Duplicate items across pages (from the sponsored-slot repeats above) are
expected; the pipeline's URL-based DuplicationPipeline already collapses
those.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://prom.ua"

_CATEGORIES = (
    "Chehly-dlya-telefonov",
    "Tehnika-i-elektronika",
    "Displej-dlya-mobilnyh-telefonov",
    "Odezhda",
    "Futbolki-muzhskie",
    "Krossovki-obuv-dlya-bega",
    "Dom-i-sad",
    "Kuhonnye-plity",
    "Krasota-i-zdorove",
    "Parfyumeriya-zhenskaya",
    "Tovary-dlya-detej",
    "Korma-dlya-domashnih-zhivotnyh",
    "Avto-moto",
    "Ukrasheniya-i-chasy",
    "Sport-i-otdykh",
)

MAX_PAGES = 15


class PromUaSpider(scrapy.Spider):
    name = "prom_ua"
    allowed_domains = ["prom.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for alias in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/ua/{alias}",
                callback=self.parse_listing,
                meta={"alias": alias, "page": 1},
            )

    def parse_listing(self, response):
        alias = response.meta["alias"]
        page = response.meta["page"]

        tiles = response.css('div[data-qaid="qa_product_tile"]')
        logger.info(f"prom_ua: {alias} page={page} tiles={len(tiles)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for tile in tiles:
            item = self._parse_tile(tile, alias, scraped_at)
            if item is not None:
                yield item

        if tiles and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/ua/{alias};{nxt}",
                callback=self.parse_listing,
                meta={"alias": alias, "page": nxt},
            )

    def _parse_tile(self, tile, alias: str, scraped_at: str) -> dict | None:
        product_id = tile.attrib.get("data-product-id")
        name = tile.css('a[data-qaid="product_link"] span::text').get()
        price = tile.css('div[data-qaid="product_price"]::attr(data-qaprice)').get()
        href = tile.css('a[data-qaid="product_link"]::attr(href)').get()

        if not name or not price or not href:
            return None
        try:
            price_val = float(price)
        except ValueError:
            return None
        if price_val <= 0:
            return None

        return {
            "product_id": product_id,
            "product_name": name.strip()[:500],
            "category": alias.replace("-", " "),
            "price": str(price_val),
            "currency": self.currency,
            "available": True,
            "url": _BASE + href if href.startswith("/") else href,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
