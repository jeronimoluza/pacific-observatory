"""
Spider for scraping Cosmed (Taiwan) - https://shop.cosmed.com.tw/
Extracts product information including prices, categories, and URLs.

Cosmed is built on the 91app platform (shopId=2131). The site is an Angular SPA
so HTML crawling only yields ~2 products. Instead, this spider uses two 91app APIs:
  1. webapi.91app.com - to fetch the full category tree
  2. fts-api.91app.com/pythia-cdn/graphql - GraphQL endpoint for paginated product listings
"""

import json
import logging
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

SHOP_ID = 2131
PAGE_SIZE = 100
CATEGORIES_URL = (
    f"https://webapi.91app.com/webapi/ShopCategory/GetShopCategoryTreeListByLevel/{SHOP_ID}"
    f"?locationId=undefined&isRetailStoreExpress=false&shopId={SHOP_ID}&lang=zh-TW"
)
GRAPHQL_URL = "https://fts-api.91app.com/pythia-cdn/graphql"
PRODUCT_PAGE_BASE = "https://shop.cosmed.com.tw/SalePage/Index"

GQL_QUERY = """query cms_shopCategory($shopId: Int!, $categoryId: Int!, $startIndex: Int!, $fetchCount: Int!, $orderBy: String) {
  shopCategory(shopId: $shopId, categoryId: $categoryId) {
    salePageList(startIndex: $startIndex, maxCount: $fetchCount, orderBy: $orderBy) {
      salePageList {
        salePageId
        title
        price
      }
      totalSize
      shopCategoryName
    }
  }
}"""


class CosmedSpider(scrapy.Spider):
    """
    Spider for Cosmed (Taiwan) using the 91app GraphQL API.
    Fetches all leaf categories then paginates through products in each.
    """

    name = "cosmed"
    allowed_domains = ["shop.cosmed.com.tw", "webapi.91app.com", "fts-api.91app.com"]
    country = "taiwan"
    currency = "TWD"

    custom_settings = {
        "DEFAULT_REQUEST_HEADERS": {
            "Referer": "https://shop.cosmed.com.tw/",
            "Accept": "application/json",
        }
    }

    def start_requests(self):
        yield scrapy.Request(CATEGORIES_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        """Fetch all leaf category IDs from the category tree."""
        data = response.json()
        category_list = data.get("Data", {}).get("List", [])
        leaf_ids = []
        self._collect_leaf_ids(category_list, leaf_ids)
        logger.info(f"Found {len(leaf_ids)} leaf categories")
        for cat_id, cat_name in leaf_ids:
            yield from self._request_category_page(cat_id, cat_name, start_index=0)

    def _collect_leaf_ids(self, lst, result):
        for item in lst:
            children = item.get("ChildList") or []
            if not item.get("IsParent") or not children:
                result.append((item["Id"], item["Name"]))
            else:
                self._collect_leaf_ids(children, result)

    def _request_category_page(self, cat_id, cat_name, start_index):
        variables = {
            "shopId": SHOP_ID,
            "categoryId": cat_id,
            "startIndex": start_index,
            "fetchCount": PAGE_SIZE,
            "orderBy": "Sales",
        }
        params = {
            "shopId": SHOP_ID,
            "lang": "zh-TW",
            "query": GQL_QUERY,
            "operationName": "cms_shopCategory",
            "variables": json.dumps(variables),
        }
        url = GRAPHQL_URL + "?" + urlencode(params)
        yield scrapy.Request(
            url,
            callback=self.parse_products,
            cb_kwargs={
                "cat_id": cat_id,
                "cat_name": cat_name,
                "start_index": start_index,
            },
        )

    def parse_products(self, response, cat_id, cat_name, start_index):
        """Parse GraphQL response and yield products; paginate if more remain."""
        data = response.json()
        sale_page_list = (
            data.get("data", {}).get("shopCategory", {}).get("salePageList", {})
        )
        products = sale_page_list.get("salePageList") or []
        total = sale_page_list.get("totalSize", 0)
        category_name = sale_page_list.get("shopCategoryName") or cat_name

        for product in products:
            sale_page_id = product.get("salePageId")
            title = product.get("title")
            price = product.get("price")
            if title and price is not None:
                yield {
                    "product_name": title,
                    "category": category_name,
                    "price": str(price),
                    "currency": self.currency,
                    "url": f"{PRODUCT_PAGE_BASE}/{sale_page_id}",
                    "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
                }

        next_index = start_index + PAGE_SIZE
        if next_index < total:
            yield from self._request_category_page(
                cat_id, cat_name, start_index=next_index
            )
