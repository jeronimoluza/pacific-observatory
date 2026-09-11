"""Shared base for ANY storefront (whatever the platform) that (a) publishes a
product sitemap and (b) renders schema.org JSON-LD or OpenGraph product meta
on its PDPs. This is the platform-agnostic sibling of `_woo_sitemap_base.py`:
where that one calls `WooBaseSpider.parse_html` (JSON-LD -> OpenGraph -> Woo-
DOM), this one stops after the first two steps via the shared
`rows_from_jsonld` / `row_from_meta` helpers in `..archived` -- the same
helpers the Common Crawl / Wayback backfiller uses for platform-agnostic
archived HTML. That makes it a fit for Wix (confirmed: Wix's own sitemap
index at /sitemap.xml links a WIX-generated `store-products-sitemap.xml`,
and Wix PDPs emit standard schema.org Product/offers JSON-LD even though the
page itself is a client-rendered SPA shell -- the JSON-LD is server-injected
for SEO and survives a plain HTTP GET), and in principle Squarespace, Odoo,
or any other platform that does the same.

Subclasses set: name, allowed_domains, currency, language, SITEMAP_URL,
PRODUCT_URL_RE, and optionally FORCE_CURRENCY when the page's own
priceCurrency is known-wrong for the tenant.

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

MAX_SITEMAPS = 40  # safety cap on <sitemapindex> fan-out
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)


class JsonLdSitemapBaseSpider(scrapy.Spider):
    name = None
    SITEMAP_URL: str = ""
    PRODUCT_URL_RE: str = r"/product"
    # Set when the PDP's own priceCurrency/OG currency is wrong for this
    # tenant. Overrides whatever rows_from_jsonld/row_from_meta read off the
    # page.
    FORCE_CURRENCY: str | None = None

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            self.SITEMAP_URL,
            callback=self.parse_sitemap,
            meta={"depth_sitemap": 0},
        )

    @staticmethod
    def _is_sitemap_loc(url: str) -> bool:
        return urlsplit(url).path.lower().endswith(".xml")

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        depth = response.meta.get("depth_sitemap", 0)
        child_maps = [u for u in locs if self._is_sitemap_loc(u)]
        pages = [u for u in locs if not self._is_sitemap_loc(u)]

        if child_maps and depth == 0:
            for url in child_maps[:MAX_SITEMAPS]:
                yield scrapy.Request(
                    url,
                    callback=self.parse_sitemap,
                    meta={"depth_sitemap": 1},
                )

        product_urls = [u for u in pages if re.search(self.PRODUCT_URL_RE, u)]
        logger.info(
            f"{self.name} sitemap={response.url} urls={len(pages)} "
            f"products={len(product_urls)} child_maps={len(child_maps)}"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        rows = rows_from_jsonld(response.text, response.url)
        if not rows:
            row = row_from_meta(response.text, response.url)
            rows = [row] if row else []
        for row in rows:
            price = row.get("price")
            if not price:
                continue
            if self.FORCE_CURRENCY:
                row["currency"] = self.FORCE_CURRENCY
            row.setdefault("currency", self.currency)
            row.setdefault("language", self.language)
            row["scraped_at_utc"] = datetime.now(timezone.utc).isoformat()
            yield row
