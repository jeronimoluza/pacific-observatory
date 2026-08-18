"""
Spider for Sodimac Peru -- https://www.sodimac.com.pe/sodimac-pe/.

Home-improvement/hardware banner (Falabella Group). NOT the same app as
homecenter_co.py (Sodimac's Colombian banner): homecenter_co runs the
newer Falabella "Catalyst" Next.js template with listing JSON at
props.pageProps.searchProps.searchData and `?currentpage=N` pagination,
discovered off a clean sitemap. Peru's robots.txt has no sitemap directive
at all and its URL scheme (`/sodimac-pe/lista/<catId>/<slug>`,
`/sodimac-pe/buscar?Ntt=...&f.product.L1_category_paths=...`) is the
legacy Falabella Endeca-commerce facet scheme -- a genuinely different
backend wearing a similar Next.js shell. Its __NEXT_DATA__ shape is also
different: listing JSON lives directly at
props.pageProps.results/pagination, each result carrying a `prices` array
of {type, crossed, price} rather than homecenter's `prices_by_type`
priority list -- the entry with crossed=false is the one actually charged
(verified live: "Canaleta PVC Blanca 10X15" showed eventPrice 8 PEN
crossed=false alongside normalPrice 9.20 PEN crossed=true). Pagination is
plain `?page=N` (confirmed live 2026-08-17 -- not homecenter's
`currentpage`).

Category discovery has no sitemap to sample, so this crawls the homepage's
own mega-menu, which SSRs all ~642 leaf category links
(`/sodimac-pe/lista/<catId>/<slug>`) directly in the raw HTML. Sampled at a
fixed stride to stay bounded, same approach as homecenter_co's sitemap
stride.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.sodimac.com.pe"
_HOME_URL = "https://www.sodimac.com.pe/sodimac-pe/"
_CATEGORY_LINK_RE = re.compile(
    r'href="(https://www\.sodimac\.com\.pe/sodimac-pe/lista/[A-Za-z0-9]+/[^"?#]*)"'
)
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
_CATEGORY_STRIDE = 6  # sample every Nth leaf category from the mega-menu
MAX_PAGES_PER_CATEGORY = 5


def _effective_price(prices: list) -> str | None:
    for p in prices:
        if p.get("crossed") is False and p.get("price"):
            return p["price"][0]
    for p in prices:
        if p.get("price"):
            return p["price"][0]
    return None


class SodimacPeSpider(scrapy.Spider):
    name = "sodimac_pe"
    allowed_domains = ["sodimac.com.pe"]
    currency = "PEN"
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
        yield scrapy.Request(_HOME_URL, callback=self.parse_home)

    def parse_home(self, response):
        urls = sorted(set(_CATEGORY_LINK_RE.findall(response.text)))
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
        category = base.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
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
            yield scrapy.Request(
                f"{base}?page={nxt}",
                callback=self.parse_listing,
                meta={"page": nxt, "base": base},
            )

    def _item(self, r: dict, category: str | None):
        name = (r.get("displayName") or "").strip()
        product_id = str(r.get("productId") or r.get("skuId") or "")
        price = _effective_price(r.get("prices") or [])
        if not name or not product_id or price is None:
            return None
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": r.get("url") or _BASE,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
