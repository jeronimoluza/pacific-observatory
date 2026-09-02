"""
Oda (formerly Kolonial.no) — Norway's leading online grocer, https://oda.com/no/.

Next.js SSR storefront. No open product-search API found (the client-side
"populært"/search pages are React-hydrated and don't expose a stable JSON
endpoint), but the site publishes a standard XML sitemap chain at
https://oda.com/sitemap.xml -> https://oda.com/sitemap/nb/products/<n>.xml
(7 pages, 1000 URLs each except the last) listing every product-detail-page
URL. Each PDP embeds a schema.org Product JSON-LD block server-side with a
clean Offer (price/priceCurrency/availability), confirmed live 2026-08-31:
'Chilinøtter' (https://oda.com/no/products/70052-r-chilinotter/) -> NOK
27.80, InStock. A sibling BreadcrumbList JSON-LD gives the category path;
the second-to-last entry is the leaf category (last entry is the product
name itself). The numeric ID prefix on the URL slug (e.g. "70052") is a
stable per-product SKU and is used as product_id.

Re-verified live 2026-08-31: GET /sitemap/nb/products/1.xml..7.xml -> 200,
6,639 total <loc> entries (page 8 -> 404, confirming the chain length).
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL_TMPL = "https://oda.com/sitemap/nb/products/{n}.xml"
_MAX_SITEMAP_PAGES = 10  # safety cap; chain is 7 pages as of 2026-08-31
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)
_PRODUCT_ID_RE = re.compile(r"/products/(\d+)-")


class OdaNoSpider(scrapy.Spider):
    name = "oda_no"
    allowed_domains = ["oda.com"]
    currency = "NOK"
    language = "no"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for n in range(1, _MAX_SITEMAP_PAGES + 1):
            yield scrapy.Request(
                _SITEMAP_URL_TMPL.format(n=n),
                callback=self.parse_sitemap,
                errback=self._ignore_missing_page,
                meta={"page": n},
                dont_filter=True,
            )

    def _ignore_missing_page(self, failure):
        logger.info("oda_no: sitemap page missing (%s), stopping chain", failure.value)

    def parse_sitemap(self, response):
        if response.status != 200:
            return
        urls = _LOC_RE.findall(response.text)
        logger.info(
            "oda_no: %d product URLs on sitemap page %s",
            len(urls),
            response.meta.get("page"),
        )
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        breadcrumb = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if not isinstance(data, dict):
                continue
            if data.get("@type") == "Product":
                product = data
            elif data.get("@type") == "BreadcrumbList":
                breadcrumb = data

        if not product:
            return

        offers = product.get("offers") or {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        category = None
        if breadcrumb:
            items = breadcrumb.get("itemListElement") or []
            if len(items) >= 2:
                category = items[-2].get("name")

        id_match = _PRODUCT_ID_RE.search(response.url)
        product_id = (
            id_match.group(1)
            if id_match
            else unquote(response.url.rstrip("/").rsplit("/", 1)[-1])
        )

        yield {
            "product_id": product_id,
            "product_name": html.unescape(str(name)).strip()[:500],
            "category": html.unescape(str(category)) if category else None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": offers.get("availability", "").endswith("InStock"),
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
