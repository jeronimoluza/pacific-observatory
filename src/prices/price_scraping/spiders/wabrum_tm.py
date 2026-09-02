"""
Wabrum (Turkmenistan) — https://wabrum.com/.

CS-Cart storefront (identified by /design/themes/.../media/images asset
paths and cart_* JS globals in the homepage source; no public REST API
found). Product-detail pages carry a full schema.org Product JSON-LD node
(sku, name, offers[0].offers[0].price, priceCurrency) plus a separate
BreadcrumbList JSON-LD node used here for category. robots.txt sets a
generic Crawl-delay: 10 for User-agent: *, but does not single out
scrapy/curl -- the project runs with ROBOTSTXT_OBEY=False globally, same
as every other spider here, so this only sets a conservative
DOWNLOAD_DELAY rather than obeying the directive literally.

Product URLs are discovered from the CS-Cart sitemap index
(sitemap.xml -> products1.xml..products5.xml, ~15-16k <loc> entries per
file). Each <loc> may carry a `?variation_id=` query for a specific
size/color; the bare URL (no query string) already resolves to one
priced SKU via schema.org, so only bare URLs are walked to avoid
re-fetching near-duplicate variant pages for a single verification run.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://wabrum.com"
SITEMAP_INDEX = f"{BASE_URL}/sitemap.xml"
_LOC_RE = re.compile(r"<loc>(.*?)</loc>")
_JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)


class WabrumTmSpider(scrapy.Spider):
    name = "wabrum_tm"
    allowed_domains = ["wabrum.com"]
    currency = "TMT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_INDEX, callback=self.parse_sitemap_index, errback=self.errback
        )

    def parse_sitemap_index(self, response):
        locs = _LOC_RE.findall(response.text)
        product_sitemaps = [loc for loc in locs if "/products" in loc]
        logger.info(f"{self.name}: product sitemap files found={len(product_sitemaps)}")
        for loc in product_sitemaps:
            yield scrapy.Request(
                loc, callback=self.parse_product_sitemap, errback=self.errback
            )

    def parse_product_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        # Bare product URLs only -- "?variation_id=" entries are the same
        # product's other sizes/colors and would just duplicate the base row.
        product_urls = [loc for loc in locs if "?" not in loc]
        logger.info(
            f"{self.name}: {response.url} entries={len(locs)} bare_products={len(product_urls)}"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        product_node = None
        breadcrumb_node = None
        for raw in _JSONLD_RE.findall(response.text):
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            node_type = str(data.get("@type", ""))
            if node_type.endswith("Product") and product_node is None:
                product_node = data
            elif node_type == "BreadcrumbList" and breadcrumb_node is None:
                breadcrumb_node = data

        if not product_node:
            return

        offers = product_node.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            return

        price = offers.get("lowPrice")
        if price is None:
            nested = offers.get("offers")
            if isinstance(nested, list) and nested:
                price = nested[0].get("price")
        currency = offers.get("priceCurrency") or self.currency
        if price is None:
            return

        name = product_node.get("name")
        if not name:
            return

        sku = product_node.get("sku") or ""

        category = None
        if breadcrumb_node:
            items = breadcrumb_node.get("itemListElement") or []
            names = [
                it.get("name")
                for it in items
                if isinstance(it, dict) and it.get("name")
            ]
            # Drop the leading "Главная" (Home) crumb and the trailing
            # product-name crumb; keep the department/subcategory chain.
            names = [n for n in names if n and n != "Главная"]
            if names and names[-1] == str(name):
                names = names[:-1]
            if names:
                category = " > ".join(names)

        availability = offers.get("availability") or ""
        available = "outofstock" not in availability.lower()

        yield {
            "product_id": sku or response.url,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": currency,
            "available": available,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
