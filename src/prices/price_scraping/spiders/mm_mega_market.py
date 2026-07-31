"""
Spider for MM Mega Market Vietnam (online.mmvietnam.com) - the online
storefront of the MM Mega Market cash-and-carry / hypermarket chain.

The site is a JS SPA, but the Magento 2 (Adobe Commerce) GraphQL endpoint
at /graphql is open and unauthenticated. The spider walks the category tree
(categoryList), collects leaf categories with products, and paginates each
via products(filter:{category_uid:{eq:...}}). Prices come back as numeric
VND in price_range.minimum_price.final_price.
"""

import base64
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://online.mmvietnam.com"
_GRAPHQL = _BASE + "/graphql"
_ROOT_ID = "2"
_PAGE_SIZE = 50

_TREE_QUERY = (
    '{ categoryList(filters:{parent_id:{eq:"%s"}}){ id product_count '
    "children{ id name product_count children{ id name product_count "
    "children{ id name product_count children{ id name product_count } } } } } }"
) % _ROOT_ID

_PRODUCTS_QUERY = (
    '{ products(filter:{category_uid:{eq:"%s"}}, pageSize:%d, currentPage:%d){ '
    "total_count page_info{ total_pages } items{ name sku url_key "
    "categories{ name } price_range{ minimum_price{ final_price{ "
    "value currency } } } } } }"
)


def _uid(category_id):
    return base64.b64encode(str(category_id).encode()).decode()


class MmMegaMarketSpider(scrapy.Spider):
    name = "mm_mega_market"
    allowed_domains = ["mmvietnam.com"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    def _gql_request(self, query, callback, meta=None):
        return scrapy.Request(
            _GRAPHQL,
            method="POST",
            body=json.dumps({"query": query}),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            callback=callback,
            meta=meta or {},
        )

    async def start(self):
        yield self._gql_request(_TREE_QUERY, self.parse_tree)

    def parse_tree(self, response):
        payload = json.loads(response.text)
        roots = (payload.get("data") or {}).get("categoryList") or []
        leaves = {}
        for root in roots:
            self._collect_leaves(root.get("children") or [], leaves)
        logger.info("mm_mega_market: %d leaf categories with products", len(leaves))
        for cid, cname in leaves.items():
            yield self._gql_request(
                _PRODUCTS_QUERY % (_uid(cid), _PAGE_SIZE, 1),
                self.parse_products,
                meta={"cid": cid, "cname": cname, "page": 1},
            )

    def _collect_leaves(self, nodes, out):
        for n in nodes:
            children = n.get("children") or []
            if children:
                self._collect_leaves(children, out)
            elif (n.get("product_count") or 0) > 0:
                out[n["id"]] = n.get("name")

    def parse_products(self, response):
        meta = response.meta
        payload = json.loads(response.text)
        block = (payload.get("data") or {}).get("products") or {}
        items = block.get("items") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            item = self._parse_item(it, meta["cname"], scraped_at)
            if item:
                yield item

        total_pages = (block.get("page_info") or {}).get("total_pages") or 1
        if meta["page"] < total_pages:
            nxt = meta["page"] + 1
            yield self._gql_request(
                _PRODUCTS_QUERY % (_uid(meta["cid"]), _PAGE_SIZE, nxt),
                self.parse_products,
                meta={"cid": meta["cid"], "cname": meta["cname"], "page": nxt},
            )

    def _parse_item(self, it, cname, scraped_at):
        name = it.get("name")
        fp = ((it.get("price_range") or {}).get("minimum_price") or {}).get(
            "final_price"
        ) or {}
        price = fp.get("value")
        if not name or price is None:
            return None
        url_key = it.get("url_key")
        cats = it.get("categories") or []
        category = cats[-1]["name"] if cats else cname
        return {
            "product_id": it.get("sku"),
            "product_name": name,
            "price": price,
            "currency": self.currency,
            "category": category,
            "url": f"{_BASE}/{url_key}.html" if url_key else _BASE,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
