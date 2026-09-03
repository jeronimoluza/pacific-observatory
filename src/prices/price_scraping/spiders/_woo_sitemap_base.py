"""
Shared base for WooCommerce/JSON-LD storefronts with NO usable Store API.

Some WooCommerce installs ship the Store API disabled, firewalled, or plainly
broken (ikuma.online returns HTTP 500 on /products while its
/products/categories works), and some storefronts are not WooCommerce at all
but still render a JSON-LD Product node per product-detail page. In both cases
the sitemap is the enumerable surface: it lists every PDP URL, and the PDP
itself carries name + price.

This walks <sitemapindex>/<urlset> from SITEMAP_URL, keeps URLs matching
PRODUCT_URL_RE, and parses each page with WooBaseSpider.parse_html -- the same
pure JSON-LD -> OpenGraph -> WooCommerce-DOM fallback chain the archive
backfiller uses, so live and archived rows come out of one code path.

Subclasses set: name, allowed_domains, currency, language, SITEMAP_URL,
PRODUCT_URL_RE, and optionally FORCE_CURRENCY when the page's own
priceCurrency is known-wrong for the tenant.

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from ._woo_base import WooBaseSpider

logger = logging.getLogger(__name__)

MAX_SITEMAPS = 40  # safety cap on <sitemapindex> fan-out
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)


class WooSitemapBaseSpider(scrapy.Spider):
    name = None
    SITEMAP_URL: str = ""
    PRODUCT_URL_RE: str = r"/product/"
    # Set when the PDP's own priceCurrency is wrong for this tenant (e.g.
    # ikuma.online emits the literal placeholder "ABC"). Overrides whatever
    # parse_html read off the page.
    FORCE_CURRENCY: str | None = None
    # Per-request TLS profile. Only takes effect when the subclass ALSO
    # disables scrapy-impersonate's RandomBrowserMiddleware, which otherwise
    # overwrites meta["impersonate"] on every request, and matches USER_AGENT
    # to the same Chrome version (curl_cffi forwards Scrapy's headers verbatim,
    # so a chrome124 handshake under a chrome120 UA is itself a 403 tell).
    # See libdelivery_lr for the full three-part override.
    IMPERSONATE_PROFILE: str | None = None

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _meta(self, extra: dict | None = None) -> dict:
        meta = dict(extra or {})
        if self.IMPERSONATE_PROFILE:
            meta["impersonate"] = self.IMPERSONATE_PROFILE
        return meta

    async def start(self):
        yield scrapy.Request(
            self.SITEMAP_URL,
            callback=self.parse_sitemap,
            meta=self._meta({"depth_sitemap": 0}),
        )

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        depth = response.meta.get("depth_sitemap", 0)
        child_maps = [u for u in locs if u.lower().endswith(".xml")]
        pages = [u for u in locs if not u.lower().endswith(".xml")]

        if child_maps and depth == 0:
            for url in child_maps[:MAX_SITEMAPS]:
                yield scrapy.Request(
                    url,
                    callback=self.parse_sitemap,
                    meta=self._meta({"depth_sitemap": 1}),
                )

        product_urls = [u for u in pages if re.search(self.PRODUCT_URL_RE, u)]
        logger.info(
            f"{self.name} sitemap={response.url} urls={len(pages)} "
            f"products={len(product_urls)} child_maps={len(child_maps)}"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, meta=self._meta())

    def parse_product(self, response):
        for row in WooBaseSpider.parse_html(response.text, response.url):
            price = row.get("price")
            if not price:
                continue
            if self.FORCE_CURRENCY:
                row["currency"] = self.FORCE_CURRENCY
            row.setdefault("currency", self.currency)
            row.setdefault("language", self.language)
            row["scraped_at_utc"] = datetime.now(timezone.utc).isoformat()
            yield row
