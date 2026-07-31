"""
Spider for SM Markets / SM Supermarket / Savemore (smmarkets.ph).

The storefront is a Magento 2 PWA whose public GraphQL endpoint
(https://smmarkets.ph/graphql) answers unauthenticated queries. This spider
walks a fixed set of food / grocery / personal-care top-level category IDs,
gathers their nested child category IDs via a single categoryList query, then
paginates the products query per category (pageSize=100), deduping by SKU
across categories. Prices are returned in PHP by minimum_price.final_price.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://smmarkets.ph"
_GRAPHQL = _BASE + "/graphql"
_PAGE_SIZE = 100

# Food / grocery / personal-care top-level category IDs (anchor categories
# whose products query includes descendants). Nested child IDs are gathered
# dynamically so leaf-only assignments are not missed.
_TARGET_PARENTS = [
    "657",  # Fresh Produce
    "660",  # Fresh Meat & Seafood
    "665",  # Frozen Goods
    "975",  # Ready To Heat & Eat Items
    "752",  # Ready to Cook
    "675",  # Chilled & Dairy Items
    "672",  # Bakery
    "756",  # International Goods
    "687",  # Pantry
    "704",  # Snacks
    "710",  # Beverage
    "1251",  # Health & Beauty
]

_CATEGORIES_QUERY = (
    "{categoryList(filters:{ids:{in:[%s]}}){id name "
    "children{id name children{id name children{id name}}}}}"
)

_PRODUCTS_QUERY = (
    '{products(filter:{category_id:{eq:"%s"}},pageSize:%d,currentPage:%d)'
    "{total_count page_info{total_pages current_page} "
    "items{name sku url_key categories{name} "
    "price_range{minimum_price{final_price{value currency}}}}}}"
)


class SmMarketsSavemoreSpider(scrapy.Spider):
    name = "sm_markets_savemore"
    allowed_domains = ["smmarkets.ph"]
    currency = "PHP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [403, 429, 500, 502, 503, 504, 408],
    }

    _UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_skus = set()

    def _graphql_request(self, query, callback, meta=None):
        return scrapy.Request(
            _GRAPHQL,
            method="POST",
            body=json.dumps({"query": query}),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": self._UA,
                "Origin": _BASE,
                "Referer": _BASE + "/",
            },
            callback=callback,
            meta=meta or {},
        )

    async def start(self):
        ids = ",".join(f'"{cid}"' for cid in _TARGET_PARENTS)
        yield self._graphql_request(_CATEGORIES_QUERY % ids, self.parse_categories)

    def _collect_ids(self, node, out):
        cid = node.get("id")
        name = node.get("name")
        if cid is not None:
            out[str(cid)] = name
        for child in node.get("children") or []:
            self._collect_ids(child, out)

    def parse_categories(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("sm_markets_savemore: non-JSON categoryList response")
            return

        cats = (payload.get("data") or {}).get("categoryList") or []
        id_to_name = {}
        for node in cats:
            self._collect_ids(node, id_to_name)

        logger.info("sm_markets_savemore: gathered %d category ids", len(id_to_name))
        for cid, name in id_to_name.items():
            yield self._graphql_request(
                _PRODUCTS_QUERY % (cid, _PAGE_SIZE, 1),
                self.parse_products,
                meta={"cid": cid, "cat_name": name, "page": 1},
            )

    def parse_products(self, response):
        cid = response.meta["cid"]
        cat_name = response.meta["cat_name"]
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("sm_markets_savemore: non-JSON products response cid=%s", cid)
            return

        products = (payload.get("data") or {}).get("products") or {}
        items = products.get("items") or []
        if not items:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            sku = item.get("sku")
            name = item.get("name")
            if not sku or not name or sku in self._seen_skus:
                continue
            price_node = (
                (item.get("price_range") or {}).get("minimum_price") or {}
            ).get("final_price") or {}
            price = price_node.get("value")
            if price is None:
                continue
            self._seen_skus.add(sku)

            item_cats = [c.get("name") for c in (item.get("categories") or []) if c]
            category = item_cats[-1] if item_cats else cat_name
            url_key = item.get("url_key")
            url = f"{_BASE}/{url_key}" if url_key else None

            yield {
                "product_id": str(sku),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        page_info = products.get("page_info") or {}
        total_pages = page_info.get("total_pages") or 1
        if page < total_pages:
            yield self._graphql_request(
                _PRODUCTS_QUERY % (cid, _PAGE_SIZE, page + 1),
                self.parse_products,
                meta={"cid": cid, "cat_name": cat_name, "page": page + 1},
            )

    def errback(self, failure):
        logger.error(
            "sm_markets_savemore: request failed %s — %r",
            failure.request.url,
            failure.value,
        )
