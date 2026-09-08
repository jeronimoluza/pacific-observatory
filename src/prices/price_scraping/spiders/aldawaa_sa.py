"""
Spider for Al-Dawaa Pharmacy (Saudi Arabia) -- https://www.al-dawaa.com/

SAP Commerce Cloud (Hybris) storefront on a Spartacus (Angular) frontend.
The live page's own <meta name="occ-backend-base-url"> declares the OCC
REST backend: https://stgprevapi.al-dawaa.com (the "stg"/"prev" naming is
just this tenant's internal hostname -- it is what the production
www.al-dawaa.com page itself calls, confirmed by reading the meta tag off
the live site, not guessed).

GET /occ/v2/aldawaa/products/search?query=<kw>&pageSize=N&currentPage=P
&fields=FULL with header Accept: application/json returns unauthenticated
JSON: no cookie, no session, no auth header. Verified live 2026-09-06 with
curl_cffi impersonate=chrome124.

Enumerability confirmed properly (not a homepage-carousel false positive):
query=vitamin -> totalResults 623, totalPages 125 at pageSize=5;
currentPage=0 vs currentPage=1 (pageSize=10) returned ZERO overlapping
product codes.

No public category-tree endpoint responded (timed out), so this walks a
fixed pharmacy/health/beauty keyword list instead
(`_aldawaa_sa_keywords.txt`), first 5 pages x 20 items/keyword, mirroring
the daraz_np keyword-seeded pattern.

price.value is already a plain decimal float in price.currencyIso (SAR
observed for every product so far -- matches countries.yaml default, but
recorded from the payload rather than assumed). url is a site-relative PDP
path; product code is the stable OCC SKU.

Page family parsed: API (spider reads the OCC JSON endpoint directly and
never fetches a rendered category or product page).
"""

import logging
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://stgprevapi.al-dawaa.com"
_SITE_BASE = "https://www.al-dawaa.com"
_KEYWORDS_PATH = Path(__file__).parent / "_aldawaa_sa_keywords.txt"
_MAX_PAGES_PER_KEYWORD = 5
_PAGE_SIZE = 20


def _load_keywords() -> list[str]:
    return [
        line.strip() for line in _KEYWORDS_PATH.read_text().splitlines() if line.strip()
    ]


class AldawaaSaSpider(scrapy.Spider):
    name = "aldawaa_sa"
    allowed_domains = ["al-dawaa.com"]
    currency = "SAR"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _search_url(self, keyword: str, page: int) -> str:
        return (
            f"{_BASE}/occ/v2/aldawaa/products/search"
            f"?query={keyword.replace(' ', '+')}&pageSize={_PAGE_SIZE}"
            f"&currentPage={page}&fields=FULL"
        )

    async def start(self):
        for kw in _load_keywords():
            yield scrapy.Request(
                self._search_url(kw, 0),
                callback=self.parse_page,
                headers={"Accept": "application/json"},
                meta={"keyword": kw, "page": 0},
            )

    def parse_page(self, response):
        keyword = response.meta["keyword"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"aldawaa_sa: non-JSON response for query={keyword} page={page}")
            return

        products = data.get("products") or []
        for p in products:
            price = p.get("price") or {}
            price_value = price.get("value")
            if price_value is None:
                continue
            url = p.get("url") or ""
            yield {
                "product_id": p.get("code"),
                "product_name": p.get("name"),
                "price": price_value,
                "currency": price.get("currencyIso", self.currency),
                "category": None,
                "url": f"{_SITE_BASE}{url}" if url else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        total_pages = (data.get("pagination") or {}).get("totalPages", 0)
        next_page = page + 1
        if products and next_page < min(total_pages, _MAX_PAGES_PER_KEYWORD):
            yield scrapy.Request(
                self._search_url(keyword, next_page),
                callback=self.parse_page,
                headers={"Accept": "application/json"},
                meta={"keyword": keyword, "page": next_page},
            )
