"""
Spider for Falabella Colombia -- https://www.falabella.com.co/falabella-co/.

Same platform and page shape as falabella_cl.py (Chile), but a genuinely
separate national storefront: falabella.com.co redirects to
/falabella-co/ (not /falabella-cl/), and its category-id space
(CATG33175, cat1001066, ...) does not overlap Chile's. Not a duplicate of
falabella_cl -- confirmed live 2026-08-17 that both domains carry
distinct catalogs/currencies (CLP vs COP).

Category discovery uses the CO sitemap (categories_co_FA_COM-0.xml, 2765
leaf categories) sampled at a fixed stride, same rationale as
falabella_cl.py.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.falabella.com.co/static/site/sitemaps/categories/categories_co_FA_COM-0.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_CATEGORY_STRIDE = 55  # sample every Nth category from the sitemap
MAX_PAGES_PER_CATEGORY = 5
_PRICE_PRIORITY = ("internetPrice", "eventPrice", "normalPrice", "cmrPrice")


class FalabellaCoSpider(scrapy.Spider):
    name = "falabella_co"
    allowed_domains = ["falabella.com.co"]
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
        pp = data.get("props", {}).get("pageProps", {})
        breadcrumbs = pp.get("breadCrumbData") or []
        category = (
            breadcrumbs[-1].get("label")
            if breadcrumbs
            else (pp.get("metadata") or {}).get("displayName")
        )
        results = pp.get("results") or []
        for r in results:
            item = self._item(r, category)
            if item:
                yield item
        pagination = pp.get("pagination") or {}
        count = pagination.get("count", 0)
        per_page = pagination.get("perPage", 48)
        if results and page < MAX_PAGES_PER_CATEGORY and page * per_page < count:
            nxt = page + 1
            sep = "&" if "?" in base else "?"
            yield scrapy.Request(
                f"{base}{sep}page={nxt}",
                callback=self.parse_listing,
                meta={"page": nxt, "base": base},
            )

    def _item(self, r: dict, category: str | None):
        name = (r.get("displayName") or "").strip()
        url = r.get("url") or ""
        if not name or not url:
            return None
        prices_by_type = {
            p["type"]: p["price"][0] for p in r.get("prices", []) if p.get("price")
        }
        price = next(
            (prices_by_type[t] for t in _PRICE_PRIORITY if t in prices_by_type), None
        )
        if price is None:
            return None
        price = price.replace(".", "").replace(",", ".")
        return {
            "product_id": str(r.get("productId") or r.get("skuId") or ""),
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
