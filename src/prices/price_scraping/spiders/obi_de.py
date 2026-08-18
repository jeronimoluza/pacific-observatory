"""
Spider for OBI Germany — https://www.obi.de/ (DIY / home-improvement).

Nuxt 3 SSR storefront. The catalog is walked via the site's own sitemap
(robots.txt -> Sitemap: /sitemaps/obi_de_de/sitemap_index.xml ->
de_pdp_index.xml -> sitemap_obi-products_N.xml), each shard holding 50000
`/p/<id>/<slug>` product URLs. Verified live 2026-08-17: shard 0 and shard 1
each returned 50000 URLs with zero product-id overlap between them —
enumerability confirmed on the sitemap itself, not a homepage.

Each PDP embeds its data in a `<script id="__NUXT_DATA__">` tag as one flat
JSON array using Vue's "devalue" serialization: nested objects don't inline
their values, they store *indices* into that same top-level array. E.g. the
price object looks like `{"grossPrice": 731, ...}` where `731` is an index,
not a price — `arr[731]` (here `75.66`) is the real EUR amount. A naive
regex for `"grossPrice":(\\d+)` returns small integers (array indices) that
look deceptively like plausible-but-wrong prices; this was the flagged trap
for this source. `currencyCode` follows the same index-indirection pattern
and resolved live to `"EUR"`. Product name is read from the plain `<title>`
tag instead (no indirection there, and simpler than chasing the several
unrelated `name` keys elsewhere in the array that belong to breadcrumbs/
attributes, not the product).
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRODUCT_ID_RE = re.compile(r"/p/(\d+)/")
_NUXT_DATA_RE = re.compile(r'id="__NUXT_DATA__">(.*?)</script>', re.DOTALL)
_TITLE_RE = re.compile(r"<title>([^<]+)</title>")
_TITLE_SUFFIX_RE = re.compile(r"\s*kaufen bei OBI\s*$")

_PRODUCT_SITEMAPS = [
    "https://www.obi.de/sitemaps/obi_de_de/sitemap_obi-products_0.xml",
    "https://www.obi.de/sitemaps/obi_de_de/sitemap_obi-products_1.xml",
    "https://www.obi.de/sitemaps/obi_de_de/sitemap_obi-products_2.xml",
]


def _resolve_devalue_number(arr: list, key: str):
    for entry in arr:
        if isinstance(entry, dict) and key in entry:
            idx = entry[key]
            if isinstance(idx, int) and 0 <= idx < len(arr):
                val = arr[idx]
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    return val
    return None


def _resolve_devalue_string(arr: list, key: str):
    for entry in arr:
        if isinstance(entry, dict) and key in entry:
            idx = entry[key]
            if isinstance(idx, int) and 0 <= idx < len(arr):
                val = arr[idx]
                if isinstance(val, str):
                    return val
    return None


class ObiDeSpider(scrapy.Spider):
    name = "obi_de"
    allowed_domains = ["obi.de"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        for url in _PRODUCT_SITEMAPS:
            yield scrapy.Request(
                url,
                callback=self.parse_sitemap,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info(f"{self.name}: {len(urls)} product URLs in {response.url}")
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        m = _PRODUCT_ID_RE.search(response.url)
        if not m:
            return
        product_id = m.group(1)

        data_m = _NUXT_DATA_RE.search(response.text)
        if not data_m:
            logger.info(f"{self.name}: no __NUXT_DATA__ at {response.url}")
            return
        try:
            arr = json.loads(data_m.group(1))
        except ValueError:
            logger.info(f"{self.name}: unparseable __NUXT_DATA__ at {response.url}")
            return

        price = _resolve_devalue_number(arr, "grossPrice")
        if price is None:
            return
        currency = _resolve_devalue_string(arr, "currencyCode") or self.currency

        title_m = _TITLE_RE.search(response.text)
        name = _TITLE_SUFFIX_RE.sub("", title_m.group(1)).strip() if title_m else None
        if not name:
            return
        name = html.unescape(name)

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": None,
            "price": str(price),
            "currency": currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
