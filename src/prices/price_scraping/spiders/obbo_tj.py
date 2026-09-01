"""Spider for Obbo (Tajikistan) — https://obbo.tj/.

CS-Cart storefront (confirmed by ``ty-breadcrumbs``/``ty-price`` markup and
``dispatch[...]`` form actions — Tygh framework naming). Self-described as a
marketplace ("Маркетплейс в Таджикистане") with a partner-onboarding page
(``/stat-partnerom/``); catalog spans electronics, home appliances,
furniture, beauty, and kids' goods — cross-division, not food.

Every product page ships a server-rendered ``schema.org/Product`` JSON-LD
block with ``offers`` in TJS (verified live 2026-09-01: iPhone 17 Pro at
12,200 TJS across 10 colour variants via a nested AggregateOffer; a plain
laptop at a single flat Offer of 2,440 TJS). Category pages carry no JSON-LD
at all (0 ``<script type="application/ld+json">`` blocks on ``/smartfony/``),
so the shared ``rows_from_jsonld`` helper naturally yields nothing for them —
safe to request every sitemap URL without pre-filtering.

Discovery uses ``/sitemap.xml`` (1397 <loc> entries, single file, no
sitemapindex) rather than walking the site's own ``/<category>/page-N/``
pagination (confirmed real — ``bytovaya-tehnika`` alone runs to page 27) —
the sitemap is bounded, robots.txt-clean (robots.txt only blocks
``items_per_page``/``sort_by`` query params, not the sitemap or its listed
URLs), and already resolves to canonical product/category pages so there is
no dedup work to do across pagination variants.

Category label comes from the last ``a.ty-breadcrumbs__a`` link on the PDP
(the immediate parent category, e.g. "iPhone" under "Смартфоны") — left null
if the breadcrumb is missing rather than invented.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

from ..archived import rows_from_jsonld

logger = logging.getLogger(__name__)

_BASE = "https://obbo.tj"
_SITEMAP_URL = f"{_BASE}/sitemap.xml"
_LOC_RE = re.compile(r"<loc>(.*?)</loc>")
_BREADCRUMB_RE = re.compile(r'class="ty-breadcrumbs__a">([^<]+)</a>')

# Non-product utility pages seen in the sitemap — harmless to request (they
# carry no JSON-LD so yield nothing) but skipped up front to save requests.
_UTILITY_SLUGS = {
    "",
    "cart",
    "catalog",
    "oformlenie-zakaza",
    "oplata-i-dostavka",
    "svyazatsya-s-nami",
    "vozvrat",
    "stat-partnerom",
    "nashi-magaziny",
}


class ObboTjSpider(scrapy.Spider):
    name = "obbo_tj"
    allowed_domains = ["obbo.tj"]
    currency = "TJS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        urls = []
        for loc in locs:
            slug = loc.rstrip("/").rsplit("/", 1)[-1]
            if slug in _UTILITY_SLUGS or loc.rstrip("/") == _BASE:
                continue
            urls.append(loc)
        logger.info("obbo_tj: sitemap has %d candidate urls", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_page)

    def parse_page(self, response):
        rows = rows_from_jsonld(response.text, response.url)
        if not rows:
            return
        category = None
        crumbs = _BREADCRUMB_RE.findall(response.text)
        if crumbs:
            category = crumbs[-1].strip()
        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in rows:
            row.setdefault("currency", self.currency)
            row.setdefault("language", self.language)
            row.setdefault("category", category)
            row.setdefault("available", True)
            if not row.get("product_id"):
                # Fallback for the rare node with no sku/productID: the PDP's
                # own URL slug is stable and unique.
                row["product_id"] = response.url.rstrip("/").rsplit("/", 1)[-1]
            row["scraped_at_utc"] = scraped_at
            yield row
