"""
Spider for scraping Guardian Singapore - https://www.guardian.com.sg/
Extracts product information including prices, categories, and URLs.

Uses the Guardian Singapore GraphQL API to fetch product data by category.
"""

import scrapy
import logging
import json

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://www.guardian.com.sg/graphql"
PAGE_SIZE = 50
MAX_PAGES = 100

# Top-level category IDs from Guardian SG GraphQL
CATEGORIES = {
    "Health": "14369",
    "Personal Care": "14378",
    "Hair Care": "14366",
    "Skin Care": "14381",
    "Makeup": "14375",
    "Men's Care": "26887",
}

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


class GuardianSGSpider(scrapy.Spider):
    """
    GraphQL API spider for Guardian Singapore.
    Fetches product data from GraphQL endpoint by category.
    """

    name = "guardian_sg"
    allowed_domains = ["www.guardian.com.sg"]
    country = "singapore"
    currency = "SGD"

    def start_requests(self):
        for cat_name, cat_id in CATEGORIES.items():
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
                            "categoryId": cat_id,
                            "pageSize": PAGE_SIZE,
                            "currentPage": 1,
                        },
                    }
                ),
                callback=self.parse_products,
                meta={"category": cat_name, "category_id": cat_id, "page": 1},
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
                "url": f"https://www.guardian.com.sg/{url_key}"
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
