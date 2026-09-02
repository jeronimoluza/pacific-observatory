"""
Mathem — Sweden's leading online grocer, https://www.mathem.se/.

Next.js SSR storefront. No open product-search API found, but the site
publishes a standard XML sitemap chain at https://www.mathem.se/sitemap.xml
-> https://www.mathem.se/sitemap/sv/products/<n>.xml (11 pages, 1000 URLs
each except the last, 10,720 product URLs total, verified live 2026-08-31).
Each PDP embeds a schema.org Product JSON-LD block server-side with a
clean Offer (price/priceCurrency/availability), confirmed live:
'Saftig Mango Torkad' (https://www.mathem.se/se/products/68984-.../) ->
SEK 89.95, InStock. A sibling BreadcrumbList JSON-LD gives the category
path; the second-to-last entry is the leaf category (last entry is the
product name itself). The numeric ID prefix on the URL slug (e.g. "68984")
is a stable per-product SKU and is used as product_id. Same platform
pattern as oda_no.py (Norway) -- Mathem merged with Oda/Kolonial.no in
2023 and now runs on Oda's tech stack; `PUBLIC_RUNTIME_MAPBOX_ACCESS_TOKEN`
in the Next.js page config is registered under Oda's "kolonialno" Mapbox
account, confirming the shared backend.

Re-verified live 2026-08-31: GET /sitemap/sv/products/1.xml..11.xml -> 200,
10,720 total <loc> entries (page 12 -> 404, confirming the chain length).
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL_TMPL = "https://www.mathem.se/sitemap/sv/products/{n}.xml"
_MAX_SITEMAP_PAGES = 15  # safety cap; chain is 11 pages as of 2026-08-31
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)
_PRODUCT_ID_RE = re.compile(r"/products/(\d+)-")


class MathemSeSpider(scrapy.Spider):
    name = "mathem_se"
    allowed_domains = ["www.mathem.se"]
    currency = "SEK"
    language = "sv"

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
        logger.info(
            "mathem_se: sitemap page missing (%s), stopping chain", failure.value
        )

    def parse_sitemap(self, response):
        if response.status != 200:
            return
        urls = _LOC_RE.findall(response.text)
        logger.info(
            "mathem_se: %d product URLs on sitemap page %s",
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
