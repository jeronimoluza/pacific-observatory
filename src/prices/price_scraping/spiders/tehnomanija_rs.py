"""
Spider for Tehnomanija (Serbia) -- https://www.tehnomanija.rs/.

Magento SSR storefront behind Cloudflare (bare requests 403 "cf-mitigated:
challenge"; chrome124 TLS impersonation via scrapy-impersonate clears it
cleanly, verified live 2026-08-17). /rest/V1/products 401s, so this uses
MagentoSSRBaseSpider's product-item-link / data-price-amount markup rather
than the REST base.

Category discovery: /rest/V1/products and a guessed nav path both 401/404;
the walkable set comes from the site's own categories.xml sitemap (541
<loc> entries), filtered to the 78 two-segment leaf paths (e.g.
bela-tehnika/frizideri) -- three-plus-segment entries in that same sitemap
are deeper sub-listings, not needed for a representative smoke pull.
Enumerability proven live: /bela-tehnika/aspiratori?p=1 vs ?p=2 return 23
+ 23 product-item-link ids with zero overlap.

Every request carries impersonate=chrome124 -- the base class does not do
this itself, so start/parse_discovery/parse_listing are overridden purely
to add the meta key onto MagentoSSRBaseSpider's existing request-building
logic (item shaping in _item is inherited unchanged).
"""

import re

import scrapy

from price_scraping.spiders import _magento_base
from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

_LEAF_CATEGORY_RE = re.compile(
    r"<loc>(https://www\.tehnomanija\.rs/[a-z0-9\-]+/[a-z0-9\-]+)</loc>"
)


class TehnomanijaRsSpider(MagentoSSRBaseSpider):
    name = "tehnomanija_rs"
    allowed_domains = ["tehnomanija.rs"]
    currency = "RSD"
    language = "sr"

    IMPERSONATE_PROFILE = "chrome124"
    DISCOVERY_URL = "https://www.tehnomanija.rs/categories.xml"
    CATEGORY_URL_RE = _LEAF_CATEGORY_RE
    PAGE_PARAM = "p"
    MAX_PAGES = 30

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            self.DISCOVERY_URL,
            callback=self.parse_discovery,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_discovery(self, response):
        urls = sorted(set(self.CATEGORY_URL_RE.findall(response.text)))
        for u in urls:
            yield scrapy.Request(
                u,
                callback=self.parse_listing,
                meta={"page": 1, "base": u, "impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_listing(self, response):
        body = response.text
        page = response.meta["page"]
        base = response.meta["base"]
        category = base.rstrip("/").split("tehnomanija.rs/", 1)[-1]
        matches = _magento_base._PRODUCT_BLOCK_RE.findall(body)
        for url, name, price in matches:
            item = self._item(url, name, price)
            if item:
                item["category"] = category
                yield item
        if matches and page < self.MAX_PAGES:
            sep = "&" if "?" in base else "?"
            nxt = page + 1
            yield scrapy.Request(
                f"{base}{sep}{self.PAGE_PARAM}={nxt}",
                callback=self.parse_listing,
                meta={
                    "page": nxt,
                    "base": base,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
            )
