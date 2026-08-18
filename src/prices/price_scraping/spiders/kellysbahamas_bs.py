"""
Spider for Kelly's (Bahamas) -- https://www.kellysbahamas.com/.

General-merchandise department store (housewares, hardware, electronics,
toys, sporting goods -- no dedicated grocery department). /products and the
sitemap's /pl//c/ category listing pages are unrendered or stale (one
sitemap category URL silent-redirected to the homepage live). The reliable,
live-verified path is the site's own schema.org SearchAction endpoint,
/s?keywords=<term>, which is plain server-rendered HTML with
product-tile__name / data-sku / product-tile__price markup and &page=N
pagination (live-checked 2026-08-17: keywords=food page=1 vs page=2 return
36 + 36 disjoint SKUs).

There is no single "browse everything" listing, so this spider seeds one
request per department name (taken from the live /c/departments nav) as a
keyword query and paginates each to its result-count ceiling.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SEARCH = "https://www.kellysbahamas.com/s?keywords={kw}&page={page}"
_DEPARTMENTS = [
    "automotive",
    "baby",
    "building supplies",
    "china",
    "electric houseware",
    "electrical",
    "general housewares",
    "hand power tools",
    "hardware fasteners",
    "home decor",
    "lawn garden",
    "linens",
    "office school supplies",
    "outdoor living",
    "paint",
    "plumbing",
    "seasonal",
    "sporting goods",
    "toys",
]
_TILE_RE = re.compile(
    r'product-tile__name"><strong>\s*([^<]+?)\s*</strong>.*?'
    r'data-sku="([^"]+)".*?'
    r'product-tile__price">\s*([^<]+?)\s*<small>',
    re.DOTALL,
)
_COUNT_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s*of\s*(\d+)")
MAX_PAGES = 20


class KellysbahamasBsSpider(scrapy.Spider):
    name = "kellysbahamas_bs"
    allowed_domains = ["kellysbahamas.com"]
    currency = "BSD"
    language = "en"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for kw in _DEPARTMENTS:
            yield self._request(kw, 1)

    def _request(self, kw: str, page: int):
        return scrapy.Request(
            _SEARCH.format(kw=kw.replace(" ", "+"), page=page),
            callback=self.parse_results,
            meta={"impersonate": "chrome124", "kw": kw, "page": page},
        )

    def parse_results(self, response):
        kw = response.meta["kw"]
        page = response.meta["page"]
        tiles = _TILE_RE.findall(response.text)
        logger.info(f"kellysbahamas_bs kw={kw!r} page={page} tiles={len(tiles)}")
        for name, sku, price in tiles:
            item = self._item(name, sku, price)
            if item:
                yield item
        m = _COUNT_RE.search(response.text)
        total = int(m.group(3)) if m else 0
        if tiles and page * 36 < total and page < MAX_PAGES:
            yield self._request(kw, page + 1)

    def _item(self, name: str, sku: str, price: str):
        name = html.unescape(name).strip()
        price = re.sub(r"[^\d.]", "", price)
        if not name or not sku or not price:
            return None
        return {
            "product_id": sku,
            "product_name": name[:500],
            "category": None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"https://www.kellysbahamas.com/s?keywords={sku}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
