"""
Spider for Home Depot Mexico -- https://www.homedepot.com.mx/.

Runs on IBM WebSphere Commerce (WCS), not the Algolia frontend suggested by
the page's JS bundle. The REST layer at /search/resources/api/v2/products
serves two distinct queries:

1. Category search (categoryId=<id>&pageNumber=N&pageSize=N) -- returns
   `contents[]` with partNumber/name/category, but price.value is always
   "0.0"/"" (unpriced placeholder).
2. Part-number batch lookup (profileName=HCL_V2_findProductByPartNumber_Details
   &partNumber=<id>&partNumber=<id2>...) -- returns the same shape but with
   real price.value populated. Batches of 20 partNumbers confirmed live.

So this is a two-hop spider: walk categories for partNumbers, then batch
those partNumbers through the pricing profile.

Category discovery uses the site's own category-tree endpoint
(/search/resources/api/v2/categories?storeId=10351&depthAndLimit=*),
found via a Playwright network trace of a real category page load (the
homepage's mega-menu hrefs are slug-only, e.g. /b/materiales-de-
construccion/..., and carry no numeric categoryId -- the tree endpoint is
the only place uniqueID/categoryId values are exposed). 767 leaf nodes
confirmed live 2026-08-17, sampled at a fixed stride.

Re-verified live 2026-08-17: categoryId=10001 (Materiales de Construcción)
page 1 -> 200, 50 contents; &pageNumber=2&pageSize=50 returned a fully
disjoint partNumber set (0 overlap with page 1) -- enumerability proven.
Part-number batch e.g. partNumber=103065P -> price.value "217.0" MXN.

robots.txt disallows legacy WCS URL patterns (CategoryDisplayView,
ProductListingView, SearchDisplay) but says nothing about
/search/resources/api/v2/ -- the REST layer used here.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.homedepot.com.mx"
_API = f"{_BASE}/search/resources/api/v2/products"
_CATEGORIES_URL = (
    f"{_BASE}/search/resources/api/v2/categories"
    "?storeId=10351&depthAndLimit=*&contractId=4000000000000000003&langId=-5"
)
_STORE_PARAMS = "storeId=10351&catalogId=10101&langId=-5&physicalStoreId=8702"
_CATEGORY_STRIDE = 12  # sample every Nth leaf category (~64 of 767)
PAGE_SIZE = 50
MAX_PAGES_PER_CATEGORY = 3
PARTNUMBER_BATCH = 20


class HomedepotMxSpider(scrapy.Spider):
    name = "homedepot_mx"
    allowed_domains = ["homedepot.com.mx"]
    currency = "MXN"
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
        yield scrapy.Request(_CATEGORIES_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: bad JSON at {response.url}")
            return
        leaves = []

        def collect(node):
            children = node.get("children") or []
            if not children:
                if node.get("uniqueID"):
                    leaves.append(node["uniqueID"])
            else:
                for child in children:
                    collect(child)

        for top in data.get("contents") or []:
            collect(top)
        sampled = leaves[::_CATEGORY_STRIDE]
        logger.info(
            f"{self.name}: sampled {len(sampled)}/{len(leaves)} leaf categories"
        )
        for cat_id in sampled:
            yield self._category_request(cat_id, page_number=1)

    def _category_request(self, cat_id, page_number):
        url = (
            f"{_API}?{_STORE_PARAMS}&categoryId={cat_id}"
            f"&pageNumber={page_number}&pageSize={PAGE_SIZE}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_category,
            meta={"cat_id": cat_id, "page_number": page_number},
        )

    def parse_category(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: bad JSON at {response.url}")
            return
        contents = data.get("contents") or []
        part_numbers = [c.get("partNumber") for c in contents if c.get("partNumber")]
        if part_numbers:
            category = None
            crumbs = data.get("breadCrumbTrailEntryView") or []
            if crumbs:
                category = crumbs[-1].get("label")
            for i in range(0, len(part_numbers), PARTNUMBER_BATCH):
                batch = part_numbers[i : i + PARTNUMBER_BATCH]
                yield self._price_request(batch, category)

        cat_id = response.meta["cat_id"]
        page_number = response.meta["page_number"]
        total = data.get("total", 0)
        if (
            part_numbers
            and page_number < MAX_PAGES_PER_CATEGORY
            and page_number * PAGE_SIZE < total
        ):
            yield self._category_request(cat_id, page_number + 1)

    def _price_request(self, part_numbers, category):
        qs = "&".join(f"partNumber={p}" for p in part_numbers)
        url = (
            f"{_API}?{_STORE_PARAMS}"
            f"&profileName=HCL_V2_findProductByPartNumber_Details&{qs}"
        )
        return scrapy.Request(
            url, callback=self.parse_prices, meta={"category": category}
        )

    def parse_prices(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: bad JSON at {response.url}")
            return
        category = response.meta.get("category")
        for c in data.get("contents") or []:
            item = self._item(c, category)
            if item:
                yield item

    def _item(self, c: dict, category: str | None):
        name = (c.get("name") or "").strip()
        part_number = c.get("partNumber")
        if not name or not part_number:
            return None
        price = None
        for p in c.get("price") or []:
            if p.get("usage") == "Offer" and p.get("value"):
                price = p["value"]
                break
        if price is None:
            for p in c.get("price") or []:
                if p.get("usage") == "Display" and p.get("value"):
                    price = p["value"]
                    break
        if not price:
            return None
        seo = c.get("seo") or {}
        href = seo.get("href")
        url = f"{_BASE}{href}" if href else _BASE
        return {
            "product_id": part_number,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
