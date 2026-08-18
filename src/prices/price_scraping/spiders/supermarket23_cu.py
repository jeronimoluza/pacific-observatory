"""
Spider for Supermarket23 (Cuba diaspora grocery delivery) --
https://www.supermarket23.com/.

Ships to Cuba, priced in USD for the sending (non-Cuban) buyer -- this is a
diaspora-priced USD signal, NOT a domestic Cuban retail price in CUP.

supermarket23.com's own Angular Universal SSR shell has zero server-rendered
price data. The real catalog lives on a separate "Treew" white-label
backend, searchengine.treew.com, discovered via Playwright network trace on
a category page. Category ids are enumerated from /sitemap.xml
(/es/categoria/<id> URLs, 240 live-checked 2026-08-17). Each category is
then paginated on searchengine.treew.com with limit/offset (live-checked:
category 1072 has total=878, offset=0 and offset=20 return disjoint
ProductId sets).

client_id=241044 identifies this specific storefront instance on the shared
Treew backend -- do not reuse for a different Treew-branded diaspora site.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://www.supermarket23.com/sitemap.xml"
_CATEGORY_RE = re.compile(r"/es/categoria/(\d+)")
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_CLIENT_ID = "241044"
_PAGE_SIZE = 50
MAX_PAGES_PER_CATEGORY = 40


class Supermarket23CuSpider(scrapy.Spider):
    name = "supermarket23_cu"
    allowed_domains = ["supermarket23.com", "searchengine.treew.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP, callback=self.parse_sitemap, meta={"impersonate": "chrome124"}
        )

    def parse_sitemap(self, response):
        cat_ids = set()
        for loc in _LOC_RE.findall(response.text):
            m = _CATEGORY_RE.search(loc)
            if m:
                cat_ids.add(m.group(1))
        logger.info(f"supermarket23_cu: {len(cat_ids)} categories in sitemap")
        for cat_id in cat_ids:
            yield self._request(cat_id, 0)

    def _request(self, cat_id: str, offset: int):
        url = (
            "https://searchengine.treew.com/category/"
            f"{cat_id}/products?client_id={_CLIENT_ID}&limit={_PAGE_SIZE}"
            f"&offset={offset}&language=SPA&currency=USD"
            "&excludedProviders=506,558&include_bodegas_products=true"
            "&only_bodegas_products=false"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"impersonate": "chrome124", "cat_id": cat_id, "offset": offset},
        )

    def parse_page(self, response):
        cat_id = response.meta["cat_id"]
        offset = response.meta["offset"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(
                f"supermarket23_cu: non-JSON response cat={cat_id} offset={offset}"
            )
            return
        products = data.get("products") or []
        logger.info(
            f"supermarket23_cu cat={cat_id} offset={offset} count={len(products)}"
        )
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if (
            len(products) >= _PAGE_SIZE
            and (offset // _PAGE_SIZE + 1) < MAX_PAGES_PER_CATEGORY
        ):
            yield self._request(cat_id, offset + _PAGE_SIZE)

    def _item(self, p: dict):
        name = html.unescape(
            (p.get("SpanishName") or p.get("EnglishName") or "").strip()
        )
        price = p.get("PriceUSD")
        product_id = p.get("ProductId")
        if not name or price is None or product_id is None:
            return None
        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": p.get("SpaCategoryName"),
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("AvailableQuantity", 0)),
            "url": f"https://www.supermarket23.com/es/producto/{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
