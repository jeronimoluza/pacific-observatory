"""
dm drogerie markt (Bosnia and Herzegovina) — https://www.dm-drogeriemarkt.ba/.

dm is a drugstore chain whose catalog is overwhelmingly personal care and
household, but it also runs a real grocery department, "Osviještena
prehrana" (Conscious Nutrition — baking, sauces/spices, breakfast,
snacks/sweets, sports nutrition, beverages, milk, coffee/tea/cocoa, side
dishes, ready meals/canned goods, tofu/meat substitutes, gluten-free), plus
"Hrana i piće za bebe i djecu" (baby/kids food and drink) under "Bebe i
djeca". This spider walks ONLY those two food-and-beverage subtrees — 64
leaf categories, discovered dynamically — rather than the whole dm catalog,
so the resulting rows are actual grocery SKUs rather than a food sliver
diluted by cosmetics.

No SSR HTML and no auth: the storefront is a client-rendered app whose data
comes from open dmtech microservices (shared platform across dm's national
sites, keyed by a country-code path segment):

1. `GET content.services.dmtech.com/rootpage-dm-shop-bs-ba?view=navigation`
   returns the full nav tree (CMS content-node ids, NOT commerce category
   ids) — used to discover the leaf category paths under the two food
   subtrees.
2. `GET content.services.dmtech.com/rootpage-dm-shop-bs-ba/<path>` (the
   category landing page's content) embeds a `DMSearchProductGrid` module
   whose `query.filters` string carries the real commerce category id, e.g.
   `"filters":"allCategories.id:041304"` — extracted via regex.
3. `GET product-search.services.dmtech.com/ba/search/static?allCategories.id=<id>
   &pageSize=100&searchType=editorial-search&sort=editorial_relevance
   &type=search-static&currentPage=<n>` returns a standard page
   (`products`, `count`, `currentPage`, `totalPages`); paginated on
   `currentPage` until `currentPage + 1 >= totalPages`.

Verified live 2026-08-31. All three endpoints are unauthenticated GETs
(confirmed via a Playwright network trace off the real category pages —
plain curl_cffi never surfaces them because the shell HTML is only ~11KB
and the grid is populated client-side). Prices ship pre-parsed in
`trackingData.price` (float, BAM — confirmed against `trackingData.currency`
and the displayed "X,XX KM"). Product id is the numeric `dan`; the PDP URL
is reconstructed from `tileData.self` ("/p/d/<dan>/<slug>").
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.dm-drogeriemarkt.ba"
NAV_URL = (
    "https://content.services.dmtech.com/rootpage-dm-shop-bs-ba"
    "?view=navigation&mrclx=false&touchpoint=web"
)
CONTENT_URL_TMPL = (
    "https://content.services.dmtech.com/rootpage-dm-shop-bs-ba{path}"
    "?mrclx=false&touchpoint=web"
)
SEARCH_URL = "https://product-search.services.dmtech.com/ba/search/static"
PAGE_SIZE = 100
_CAT_ID_RE = re.compile(r"allCategories\.id:(\d+)")

FOOD_ROOTS = (
    "/osvijestena-prehrana",
    "/bebe-i-djeca/hrana-i-pice-za-bebe-i-djecu",
)


class DmBaSpider(scrapy.Spider):
    name = "dm_ba"
    allowed_domains = ["dmtech.com", "dm-drogeriemarkt.ba"]
    currency = "BAM"
    language = "bs"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
    }

    async def start(self):
        yield scrapy.Request(NAV_URL, callback=self.parse_nav, errback=self.errback)

    def parse_nav(self, response):
        nav = response.json()
        leaves: list[str] = []
        self._collect_leaves(nav.get("navigation", {}), False, leaves)
        logger.info(f"{self.name}: {len(leaves)} food/beverage leaf categories")
        for path in leaves:
            yield scrapy.Request(
                CONTENT_URL_TMPL.format(path=path),
                callback=self.parse_content,
                errback=self.errback,
                meta={"path": path},
            )

    def _collect_leaves(self, node, in_food, out):
        link = node.get("link") or ""
        is_food_root = any(
            link == root or link.startswith(root + "/") for root in FOOD_ROOTS
        )
        now_in_food = in_food or is_food_root
        children = node.get("children") or []
        if now_in_food and not children and link.startswith("/"):
            out.append(link)
        for child in children:
            self._collect_leaves(child, now_in_food, out)

    def parse_content(self, response):
        path = response.meta["path"]
        m = _CAT_ID_RE.search(response.text)
        if not m:
            logger.warning(f"{self.name}: no category id found for {path}")
            return
        category_id = m.group(1)
        yield self._search_request(category_id, path, page=0)

    def _search_request(self, category_id, path, page):
        params = (
            f"allCategories.id={category_id}&pageSize={PAGE_SIZE}"
            f"&searchType=editorial-search&sort=editorial_relevance"
            f"&type=search-static&currentPage={page}"
        )
        return scrapy.Request(
            f"{SEARCH_URL}?{params}",
            callback=self.parse_search,
            errback=self.errback,
            meta={"category_id": category_id, "path": path, "page": page},
            dont_filter=True,
        )

    def parse_search(self, response):
        category_id = response.meta["category_id"]
        path = response.meta["path"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        for product in data.get("products") or []:
            tile = product.get("tileData") or {}
            title = (tile.get("title") or {}).get("tileHeadline") or product.get(
                "title"
            )
            if not title:
                continue
            tracking = tile.get("trackingData") or {}
            price = tracking.get("price")
            if price is None:
                continue
            currency = tracking.get("currency") or self.currency
            categories = tracking.get("categories") or []
            self_path = tile.get("self") or ""
            dan = tile.get("dan") or product.get("dan")
            yield {
                "product_id": str(dan) if dan else self_path,
                "product_name": str(title).strip()[:500],
                "category": categories[0] if categories else None,
                "price": str(price),
                "currency": currency,
                "available": True,
                "url": f"{BASE_URL}{self_path}" if self_path else response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        total_pages = data.get("totalPages") or 0
        logger.info(
            f"{self.name}: path={path} category_id={category_id} page={page} "
            f"got={len(data.get('products') or [])} count={data.get('count')} "
            f"totalPages={total_pages}"
        )
        if page + 1 < total_pages:
            yield self._search_request(category_id, path, page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
