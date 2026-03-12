"""
Spider for scraping Mannings (Hong Kong) - https://www.mannings.com.hk/
Extracts product information including prices, categories, and URLs.

Uses the Mannings GraphQL API to fetch product data by category.
"""

import scrapy
import logging
import json

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://www.mannings.com.hk/graphql"
PAGE_SIZE = 50
MAX_PAGES = 100

# Top-level category IDs from Mannings GraphQL
CATEGORIES = {
    "Food & Confectionery": "8853",
    "Beauty": "8854",
    "Hair": "8855",
    "Health": "8856",
    "Household": "8857",
    "Mom & Baby": "8858",
    "Personal Care": "8859",
}


CATEGORY_CHILDREN_QUERY = """
query GetCategoryChildren($categoryId: Int!) {
  category(id: $categoryId) {
    id
    name
    children {
      id
      name
    }
  }
}
"""

PRODUCTS_QUERY = """
query GetProducts($categoryId: String!, $pageSize: Int!, $currentPage: Int!) {
  products(
    filter: { category_id: { eq: $categoryId } }
    pageSize: $pageSize
    currentPage: $currentPage
  ) {
    items {
      name
      sku
      price_range {
        minimum_price {
          final_price {
            value
            currency
          }
        }
      }
      url_key
    }
    total_count
  }
}
"""


class ManningsSpider(scrapy.Spider):
    """
    GraphQL API spider for Mannings (Hong Kong).
    Fetches product data from GraphQL endpoint by category.
    """

    name = "mannings"
    allowed_domains = ["www.mannings.com.hk"]
    country = "hong_kong"
    currency = "HKD"
    # P0 hardening: GraphQL returns empty product sets in current environment.
    # Keep the spider code for later fixing, but do not run it in bulk jobs.
    active = False

    def _request(self, body: dict, callback, meta: dict) -> scrapy.Request:
        return scrapy.Request(
            GRAPHQL_URL,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(body),
            callback=callback,
            meta=meta,
        )

    def start_requests(self):
        # Mannings does not always assign products directly to the parent category;
        # fetch children and scrape each child category id.
        for cat_name, cat_id in CATEGORIES.items():
            yield self._request(
                body={
                    "query": CATEGORY_CHILDREN_QUERY,
                    "operationName": "GetCategoryChildren",
                    "variables": {"categoryId": int(cat_id)},
                },
                callback=self.parse_category_children,
                meta={"parent_category": cat_name, "parent_category_id": cat_id},
            )

    def parse_category_children(self, response):
        parent_name = response.meta["parent_category"]
        parent_id = response.meta["parent_category_id"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from %s", response.url)
            return

        category = (data.get("data") or {}).get("category") or {}
        children = category.get("children") or []

        # Fallback: if no children are returned, try the parent id directly.
        targets: list[tuple[str, str]] = []
        for child in children:
            child_id = child.get("id")
            child_name = child.get("name")
            if child_id is None:
                continue
            label = f"{parent_name} > {child_name}" if child_name else parent_name
            targets.append((label, str(child_id)))

        if not targets:
            targets = [(parent_name, parent_id)]

        for label, cat_id in targets:
            yield self._request(
                body={
                    "query": PRODUCTS_QUERY,
                    "operationName": "GetProducts",
                    "variables": {
                        "categoryId": cat_id,
                        "pageSize": PAGE_SIZE,
                        "currentPage": 1,
                    },
                },
                callback=self.parse_products,
                meta={"category": label, "category_id": cat_id, "page": 1},
            )

    def parse_products(self, response):
        """Parse GraphQL product response."""
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from {response.url}")
            return

        products_data = data.get("data", {}).get("products", {})
        items = products_data.get("items", [])
        total_count = products_data.get("total_count", 0)
        category = response.meta["category"]
        category_id = response.meta["category_id"]
        current_page = response.meta["page"]

        logger.info(
            f"{category} page {current_page}: {len(items)} products (total: {total_count})"
        )

        for item in items:
            name = item.get("name")
            price_info = (
                item.get("price_range", {})
                .get("minimum_price", {})
                .get("final_price", {})
            )
            price = price_info.get("value")
            url_key = item.get("url_key", "")

            if not name or price is None:
                continue

            yield {
                "product_name": name.strip(),
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "url": f"https://www.mannings.com.hk/{url_key}"
                if url_key
                else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        # Paginate
        total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE if total_count else 0
        if current_page < min(total_pages, MAX_PAGES) and len(items) > 0:
            next_page = current_page + 1
            yield scrapy.Request(
                GRAPHQL_URL,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body=json.dumps(
                    {
                        "query": PRODUCTS_QUERY,
                        "operationName": "GetProducts",
                        "variables": {
                            "categoryId": category_id,
                            "pageSize": PAGE_SIZE,
                            "currentPage": next_page,
                        },
                    }
                ),
                callback=self.parse_products,
                meta={
                    "category": category,
                    "category_id": category_id,
                    "page": next_page,
                },
            )
