"""
Spider for Homecenter Colombia (Sodimac) -- https://www.homecenter.com.co/.

Runs on the same Falabella-Group Next.js platform as falabella_cl.py /
falabella_co.py (shared businessUnit/tenant/catalystBaseUrl fields and
media.falabella.com CDN in __NEXT_DATA__), but a distinct app template:
listing JSON lives at props.pageProps.searchProps.searchData
(results/pagination), not props.pageProps directly. Pagination query
param is `currentpage` (confirmed live -- `?page=N` is a no-op here,
unlike the falabella_* sites).

Category discovery uses the site's own category sitemap
(sodimac-catalyst-bu-prod-browse-sitemaps/soco-browse-category-sitemap.xml,
2220 leaf categories) sampled at a fixed stride to stay bounded.

Product URLs omit the slug (`/homecenter-co/product/{productId}`) --
confirmed live 2026-08-17 this 200s and redirects to the full canonical
PDP, so no slug reconstruction is needed.

Re-verified live 2026-08-17: GET category cat10019/cortacesped -> 200,
real COP prices e.g. type":"NORMAL","price":"1.499.900".
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.homecenter.com.co"
_SITEMAP_URL = (
    "https://www.homecenter.com.co/sodimac-catalyst-bu-prod-browse-sitemaps/"
    "soco-browse-category-sitemap.xml"
)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_CATEGORY_STRIDE = 55  # sample every Nth category from the sitemap
MAX_PAGES_PER_CATEGORY = 5
_PRICE_PRIORITY = ("INTERNET", "NORMAL", "CMR")


class HomecenterCoSpider(scrapy.Spider):
    name = "homecenter_co"
    allowed_domains = ["homecenter.com.co"]
    currency = "COP"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        sampled = urls[::_CATEGORY_STRIDE]
        logger.info(f"{self.name}: sampled {len(sampled)}/{len(urls)} categories")
        for url in sampled:
            yield scrapy.Request(
                url, callback=self.parse_listing, meta={"page": 1, "base": url}
            )

    def parse_listing(self, response):
        page = response.meta["page"]
        base = response.meta["base"]
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"{self.name}: no __NEXT_DATA__ at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning(f"{self.name}: bad __NEXT_DATA__ JSON at {response.url}")
            return
        page_props = data.get("props", {}).get("pageProps", {})
        search_data = page_props.get("searchProps", {}).get("searchData", {})
        category_results = (
            page_props.get("categoryProps", {})
            .get("categoryData", {})
            .get("results", {})
        )
        category = category_results.get("displayName")
        results = search_data.get("results") or []
        for r in results:
            item = self._item(r, category)
            if item:
                yield item
        pagination = search_data.get("pagination") or {}
        count = pagination.get("count", 0)
        per_page = pagination.get("perPage", 40)
        if results and page < MAX_PAGES_PER_CATEGORY and page * per_page < count:
            nxt = page + 1
            sep = "&" if "?" in base else "?"
            yield scrapy.Request(
                f"{base}{sep}currentpage={nxt}",
                callback=self.parse_listing,
                meta={"page": nxt, "base": base},
            )

    def _item(self, r: dict, category: str | None):
        name = (r.get("displayName") or "").strip()
        product_id = str(r.get("productId") or r.get("skuId") or "")
        if not name or not product_id:
            return None
        prices_by_type = {
            p["type"]: p["price"] for p in r.get("prices", []) if p.get("price")
        }
        price = next(
            (prices_by_type[t] for t in _PRICE_PRIORITY if t in prices_by_type), None
        )
        if price is None:
            return None
        price = price.replace(".", "").replace(",", ".")
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/homecenter-co/product/{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
