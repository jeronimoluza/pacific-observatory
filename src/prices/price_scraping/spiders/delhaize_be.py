"""
Spider for Delhaize Belgium -- https://www.delhaize.be/.

Next.js storefront (Ahold Delhaize group, same corporate family as ah.be --
but a DIFFERENT backend: ah.be sits behind an Akamai edge that 403s even the
mobile-app auth endpoint, delhaize.be does not). robots.txt exposes
`/sitemap/delhaizesitemapindex.xml` -> a single gzipped urlset of ~22.7k
category-listing urls (`.../c/<categoryCode>`, e.g. `v2FRUFRUKIW` for Kiwis).

Category pages are client-hydrated (no product data in the server HTML or
in `__NEXT_DATA__.apolloState`, which only carries `ROOT_QUERY`) -- a
Playwright network trace found the real backend: a public Apollo GraphQL
persisted-query endpoint, `GET /api/v1/?operationName=
GetCategoryProductSearch&variables={...,"category":"<code>",
"pageNumber":N,"pageSize":48,...}&extensions={"persistedQuery":
{"version":1,"sha256Hash":"d8bff3916275ffeb6f51604d36d7a3aa2f9cd92847487a7f2e3bdf6bb2115cdd"}}`.
Plain curl_cffi 400s with a CSRF error unless an `apollo-require-preflight:
true` header is sent -- no cookies, no auth token needed otherwise.

Verified live 2026-09-06: category v2FRUFRUKIW (Kiwis) returned 4 real
products, e.g. "Kiwi | Jaune | 6pc", EUR 5.49 (`price.value`,
`price.currencyIso`). Page family: API (spider never fetches a rendered
page; the sitemap is only used to harvest category codes).
"""

import gzip
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.delhaize.be/sitemap/delhaizesitemapindex.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_CAT_CODE_RE = re.compile(r"/c/([A-Za-z0-9]+)$")
_SHA256_HASH = "d8bff3916275ffeb6f51604d36d7a3aa2f9cd92847487a7f2e3bdf6bb2115cdd"
_PAGE_SIZE = 48
_CATEGORY_STRIDE = 20  # sample every Nth category to keep the crawl bounded


def _search_url(category: str) -> str:
    variables = {
        "lang": "fr",
        "searchQuery": "",
        "category": category,
        "pageNumber": 0,
        "pageSize": _PAGE_SIZE,
        "filterFlag": True,
        "fields": "PRODUCT_TILE",
        "plainChildCategories": True,
    }
    extensions = {"persistedQuery": {"version": 1, "sha256Hash": _SHA256_HASH}}
    return (
        "https://www.delhaize.be/api/v1/?operationName=GetCategoryProductSearch"
        f"&variables={quote(json.dumps(variables))}"
        f"&extensions={quote(json.dumps(extensions))}"
    )


class DelhaizeBeSpider(scrapy.Spider):
    name = "delhaize_be"
    allowed_domains = ["delhaize.be"]
    currency = "EUR"
    language = "fr"

    IMPERSONATE_PROFILE = "chrome124"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_sitemap_index(self, response):
        shards = _LOC_RE.findall(response.text)
        logger.info("delhaize_be: %d sitemap shards", len(shards))
        for shard in shards:
            yield scrapy.Request(
                shard,
                callback=self.parse_sitemap_shard,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_sitemap_shard(self, response):
        try:
            xml_text = gzip.decompress(response.body).decode("utf-8")
        except OSError:
            xml_text = response.text
        locs = _LOC_RE.findall(xml_text)
        categories = []
        seen = set()
        for loc in locs:
            m = _CAT_CODE_RE.search(loc)
            if not m:
                continue
            code = m.group(1)
            if code in seen:
                continue
            seen.add(code)
            categories.append(code)
        sampled = categories[::_CATEGORY_STRIDE]
        logger.info(
            "delhaize_be: sampled %d/%d categories from %s",
            len(sampled), len(categories), response.url,
        )
        for code in sampled:
            yield scrapy.Request(
                _search_url(code),
                callback=self.parse_search,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "category": code},
                headers={"Accept": "application/json", "apollo-require-preflight": "true"},
            )

    def parse_search(self, response):
        category = response.meta["category"]
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("delhaize_be: non-JSON response for category=%s", category)
            return

        result = ((data.get("data") or {}).get("categoryProductSearch") or {})
        products = result.get("products") or []
        for p in products:
            price = p.get("price") or {}
            value = price.get("value")
            name = p.get("name")
            if not name or value in (None, "", 0):
                continue
            first_cat = p.get("firstLevelCategory") or {}
            yield {
                "product_id": p.get("code"),
                "product_name": str(name).strip()[:500],
                "category": first_cat.get("name") or category,
                "price": str(value),
                "currency": price.get("currencyIso") or self.currency,
                "available": bool(p.get("available")),
                "url": "https://www.delhaize.be" + p.get("url", "") if p.get("url") else response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
