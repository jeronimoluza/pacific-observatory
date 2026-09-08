"""
Spider for Mega Image (Romania) -- https://www.mega-image.ro/.

Mega Image is Ahold Delhaize's Romanian banner (confirmed via robots.txt
`Sitemap: .../sitemap/delhaizesitemapindex.xml` and the Google Play
package `ro.delhaize`). The corporate homepage carries no visible
shop-browsing nav, but the storefront itself is a fully working Next.js
app with an Apollo-persisted-query GraphQL API at `/api/v1/`.

Category listing pages call `GetCategoryProductSearch` (found via
Playwright network trace on a category URL, e.g.
`/Dulciuri-si-snacks/Ciocolata/Tablete-de-ciocolata/c/006001003`):

  GET /api/v1/?operationName=GetCategoryProductSearch
      &variables={"lang":"ro","searchQuery":"","category":"<code>",
                  "pageNumber":<N>,"pageSize":20,"filterFlag":true,
                  "fields":"PRODUCT_TILE","plainChildCategories":true}
      &extensions={"persistedQuery":{"version":1,
                  "sha256Hash":"d8bff3916275ffeb6f51604d36d7a3aa2f9cd92847487a7f2e3bdf6bb2115cdd"}}

This 400s with "potential CSRF" unless an `apollo-require-preflight` (or
`x-apollo-operation-name`) header is present -- no cookie/session needed
otherwise. Verified live 2026-09-06 with plain curl_cffi, no auth.
Response carries `pagination.totalPages` for clean termination.

372 leaf category codes harvested from the gzipped Delhaize sitemap
(`delhaizesitemap-0.xml.gz`, `<xhtml:link href=".../c/<code>"/>` entries;
452 total codes, reduced to leaves by dropping any code that is a
string-prefix of another code in the set) -- listed in
`_mega_image_ro_categories.txt`.

Confirmed live 2026-09-06: category 006001003 "Tablete de ciocolata",
code 39614 "Ciocolata amaruie 85% cacao 80g" RON 14.99 (price.value,
decimal RON, no minor-unit scaling). AI_NOTES' loyalty/CONNECT tiered
price is present on some tiles (`wasPrice`/promo fields) but not
captured -- single headline `price.value` only, matching the
billa_at/billa_cz convention of not splitting conditional price tiers.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.mega-image.ro"
_API = f"{_BASE}/api/v1/"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_mega_image_ro_categories.txt"
_PERSISTED_HASH = "d8bff3916275ffeb6f51604d36d7a3aa2f9cd92847487a7f2e3bdf6bb2115cdd"
PAGE_SIZE = 20
MAX_PAGES = 30  # safety cap per category (30 * 20 = 600 items/category)


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class MegaImageRoSpider(scrapy.Spider):
    name = "mega_image_ro"
    allowed_domains = ["mega-image.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Referer": "https://www.mega-image.ro/",
            "apollo-require-preflight": "true",
            "x-apollo-operation-name": "GetCategoryProductSearch",
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_codes = set()

    def _request(self, category: str, page: int):
        variables = {
            "lang": "ro",
            "searchQuery": "",
            "category": category,
            "pageNumber": page,
            "pageSize": PAGE_SIZE,
            "filterFlag": True,
            "fields": "PRODUCT_TILE",
            "plainChildCategories": True,
        }
        extensions = {"persistedQuery": {"version": 1, "sha256Hash": _PERSISTED_HASH}}
        params = {
            "operationName": "GetCategoryProductSearch",
            "variables": json.dumps(variables),
            "extensions": json.dumps(extensions),
        }
        return scrapy.Request(
            f"{_API}?{urlencode(params)}",
            callback=self.parse_category,
            meta={"category": category, "page": page},
        )

    def start_requests(self):
        for cat in _load_categories():
            yield self._request(cat, 0)

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            return
        result = (data.get("data") or {}).get("categoryProductSearch") or {}
        products = result.get("products") or []
        logger.info(f"mega_image_ro: cat={category} page={page} products={len(products)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            code = p.get("code")
            if not code or code in self._seen_codes:
                continue
            price = p.get("price") or {}
            value = price.get("value")
            name = (p.get("name") or "").strip()
            if not name or value is None:
                continue
            self._seen_codes.add(code)
            cat_info = p.get("firstLevelCategory") or {}
            yield {
                "product_id": code,
                "product_name": name[:500],
                "category": cat_info.get("name"),
                "price": value,
                "currency": price.get("currencyIso", self.currency),
                "available": bool(p.get("available", True)),
                "url": f"{_BASE}{p.get('url')}" if p.get("url") else None,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        pagination = result.get("pagination") or {}
        total_pages = pagination.get("totalPages") or 0
        if page + 1 < total_pages and page + 1 < MAX_PAGES:
            yield self._request(category, page + 1)
