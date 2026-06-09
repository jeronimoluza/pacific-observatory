"""
Spider for MH Online (Fiji) — Morris Hedstrom's WooCommerce storefront.

URL discovery via the WordPress sitemap index `/wp-sitemap.xml` which exposes
`/wp-sitemap-posts-product-*.xml` (~3,700 canonical product URLs). This avoids
the BFS-from-`/shop/` strategy used previously, which discovered thousands of
duplicate variant URLs of the form `/product/<slug>/<post-id>` that all 301
back to the canonical `/product/<slug>/` — wasting most of the request budget
on redirect chains.

Each product page exposes a Schema.org Product JSON-LD inside a `@graph` array
(alongside a BreadcrumbList); we read name, sku, brand, offers.price,
offers.priceCurrency, offers.availability from it.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_INDEX = "https://mh.com.fj/wp-sitemap.xml"
# Strip a trailing /<digits> from product URLs so the variant suffixes don't
# round-trip through 301 redirects to the canonical slug.
VARIANT_SUFFIX_RE = re.compile(r"/\d+/?$")


class MhOnlineSpider(scrapy.Spider):
    name = "mh_online"
    allowed_domains = ["mh.com.fj"]
    currency = "FJ"
    language = "en"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        # Site is responsive and returns no 429s; AutoThrottle was capping us
        # at ~15 items/min in the previous run.
        "AUTOTHROTTLE_ENABLED": False,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queued_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(
            SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={
                "impersonate": self.IMPERSONATE_PROFILE,
                "handle_httpstatus_list": [404],
            },
            errback=self.errback,
        )

    def parse_sitemap_index(self, response):
        sub_sitemaps = response.xpath("//*[local-name()='loc']/text()").getall()
        product_sitemaps = [s for s in sub_sitemaps if "posts-product" in s]
        logger.info(
            f"sitemap index: {len(sub_sitemaps)} sub-sitemaps "
            f"({len(product_sitemaps)} product sub-sitemaps)"
        )
        for sm in product_sitemaps:
            # Site quirk: some sub-sitemaps return HTTP 404 with a valid XML
            # payload (e.g. wp-sitemap-posts-product-2.xml on 2026-05-21
            # served 404 + 1,702 product URLs). Accept 404 here so the body
            # still reaches the parser.
            yield scrapy.Request(
                sm,
                callback=self.parse_product_sitemap,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "handle_httpstatus_list": [404],
                },
                errback=self.errback,
            )

    def parse_product_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        canonical = []
        for u in urls:
            cu = VARIANT_SUFFIX_RE.sub("/", u)
            if cu in self.queued_urls:
                continue
            self.queued_urls.add(cu)
            canonical.append(cu)
        logger.info(
            f"{response.url.rsplit('/', 1)[-1]}: {len(urls)} urls, queued {len(canonical)}"
        )
        for url in canonical:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
                errback=self.errback,
            )

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
            return
        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        # WooCommerce ships price under offers[0].priceSpecification[0].price,
        # not as a top-level offer.price.
        price = offer.get("price")
        currency = offer.get("priceCurrency")
        if price is None:
            specs = offer.get("priceSpecification") or []
            if isinstance(specs, dict):
                specs = [specs]
            if specs:
                price = specs[0].get("price")
                currency = currency or specs[0].get("priceCurrency")
        name = product.get("name")
        if not (price and name):
            return
        brand = product.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        yield {
            "product_id": str(product.get("sku") or product.get("@id") or response.url),
            "product_name": str(name).strip()[:500],
            "brand": brand,
            "category": self._extract_category(response),
            "price": str(price),
            "currency": currency or self.currency,
            "available": "InStock" in str(offer.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_product(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Product":
                    return c
        return None

    @staticmethod
    def _extract_category(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "BreadcrumbList":
                    crumbs = c.get("itemListElement") or []
                    names = []
                    for cr in crumbs:
                        item = cr.get("item") if isinstance(cr, dict) else None
                        if isinstance(item, dict) and item.get("name"):
                            names.append(item["name"])
                    if names:
                        return " > ".join(names)
        return None

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
