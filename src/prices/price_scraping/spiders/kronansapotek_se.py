"""
Kronans Apotek — one of Sweden's largest pharmacy chains,
https://www.kronansapotek.se/.

Gatsby-built storefront (meta generator "Gatsby 5.16.1"). Product/category
URLs are enumerated by a standard XML sitemap chain:

    https://www.kronansapotek.se/_gatsby/sitemap-index.xml
        -> https://www.kronansapotek.se/_gatsby/sitemap-<n>.xml (n=0..7)

Verified live 2026-08-31: 8 sitemap pages, 37,532 <loc> entries total,
33,940 of them product-detail pages matching the `/p/<sku>/` path shape
(the remainder are `/c/<slug>/` category pages, filtered out).

Each PDP embeds a single `<script type="application/ld+json">` tag whose
body is a JSON *array* of two objects -- schema.org Product (name, sku,
offers.price/priceCurrency/availability) and BreadcrumbList (category
path) -- both server-rendered, no client-side fetch needed. Sample
verified: 'Ibetin 200 mg Ibuprofen ... 100 tablett(er)' (sku 027263) ->
SEK 107.15, InStock. `sku` is the stable product_id; category is taken
from the BreadcrumbList's second-to-last item (last item duplicates the
product name).

Currency SEK, tax-inclusive, matches countries.yaml. Channel: pharmacy --
built as Sweden's 5th source after 3 confirmed food/grocery sources
(rekoekologiska_se, koro_se, mathem_se) plus the beverage-of-record
systembolaget_se; pharmacy is legitimate infill per onboarding priority
rules, not a substitute for grocery coverage.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL_TMPL = "https://www.kronansapotek.se/_gatsby/sitemap-{n}.xml"
_MAX_SITEMAP_PAGES = 10  # safety cap; chain is 8 pages (0..7) as of 2026-08-31
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)
_PRODUCT_PATH_RE = re.compile(r"/p/[^/?]+/?$")


class KronansapotekSeSpider(scrapy.Spider):
    name = "kronansapotek_se"
    allowed_domains = ["www.kronansapotek.se"]
    currency = "SEK"
    language = "sv"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for n in range(_MAX_SITEMAP_PAGES):
            yield scrapy.Request(
                _SITEMAP_URL_TMPL.format(n=n),
                callback=self.parse_sitemap,
                errback=self._ignore_missing_page,
                meta={"page": n},
                dont_filter=True,
            )

    def _ignore_missing_page(self, failure):
        logger.info(
            "kronansapotek_se: sitemap page missing (%s), stopping chain",
            failure.value,
        )

    def parse_sitemap(self, response):
        if response.status != 200:
            return
        locs = _LOC_RE.findall(response.text)
        urls = [u for u in locs if _PRODUCT_PATH_RE.search(u)]
        logger.info(
            "kronansapotek_se: %d/%d product URLs on sitemap page %s",
            len(urls),
            len(locs),
            response.meta.get("page"),
        )
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        breadcrumb = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") == "Product":
                    product = item
                elif item.get("@type") == "BreadcrumbList":
                    breadcrumb = item

        if not product:
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        sku = product.get("sku")
        if not name or not sku or price in (None, "", 0, "0"):
            return

        category = None
        if breadcrumb:
            items = breadcrumb.get("itemListElement") or []
            if len(items) >= 2:
                category = items[-2].get("name")

        yield {
            "product_id": str(sku),
            "product_name": str(name).strip()[:500],
            "category": category or None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(offers.get("availability", "")).endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
