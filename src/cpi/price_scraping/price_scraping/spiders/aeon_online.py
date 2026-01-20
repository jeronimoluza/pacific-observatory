"""
Spider for scraping Aeon Online (Cambodia) - https://aeononlineshopping.com/
Extracts product information including prices, categories, store locations, and URLs.
Uses the JSON API directly (no Playwright needed).

Strategy:
1. Fetch store API which returns featured products and category tree
2. Extract products from the store response
3. Build category mapping from the category tree
4. Track scraped product IDs to avoid duplicates across stores
"""

import scrapy
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class AeonOnlineSpider(scrapy.Spider):
    """
    Spider for Aeon Online (Cambodia).
    Uses JSON API directly to extract product data.
    Extracts products from store API response.
    """

    name = "aeon_online"
    allowed_domains = ["aeononlineshopping.com"]
    country = "cambodia"
    currency = "KHR"

    # Store slugs to scrape
    STORE_SLUGS = [
        "aeon1-aeon-phnom-penh",
        "aeon2-aeon-sen-sok",
        "aeon3-aeon-mean-chey",
        "maxvalu-toul-kork",
        "maxvalu-boeung-kak",
        "aeon1-aeon-food-phnom-penh",
        "aeon2-aeon-food-sen-sok",
        "aeon3-aeon-food-mean-chey",
        "aeon3-fashion-beauty",
        "maxvalu-tuek-thla",
        "maxvalu-express-reoussey-keo-598",
        "maxvalu-tonle-bassac-monivong",
    ]

    # API endpoints
    STORE_API = "https://aeononlineshopping.com/api/store/{store_slug}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track scraped product IDs to avoid duplicates across stores
        self.scraped_product_ids = set()

    def start_requests(self):
        """
        Generate requests for each store's API endpoint.
        """
        for store_slug in self.STORE_SLUGS:
            url = self.STORE_API.format(store_slug=store_slug)
            yield scrapy.Request(
                url,
                callback=self.parse_store_api,
                meta={"store_slug": store_slug},
                headers={"Accept": "application/json"},
            )

    def parse_store_api(self, response):
        """
        Parse store API response to extract products.
        The store API returns featured products and category tree.
        """
        store_slug = response.meta.get("store_slug")

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON for store {store_slug}")
            return

        # Extract store info
        store_info = data.get("store", {})
        store_id = store_info.get("store_id")
        store_name = store_info.get("name", store_slug)

        logger.info(f"Parsing store: {store_name} (ID: {store_id})")

        # Build category lookup from the category tree
        categories = data.get("categories", [])
        category_lookup = self._build_category_lookup(categories)

        logger.info(f"Built category lookup with {len(category_lookup)} categories")

        scraped_at = datetime.utcnow().isoformat()
        new_products_count = 0

        # Extract products from the main products array
        products = data.get("products", [])
        logger.info(f"Found {len(products)} featured products for store {store_name}")

        for product in products:
            item = self._extract_product_from_api(
                product, store_slug, store_name, store_id, category_lookup, scraped_at
            )
            if item:
                product_id = item.get("product_id")
                if product_id and product_id in self.scraped_product_ids:
                    continue
                if product_id:
                    self.scraped_product_ids.add(product_id)
                new_products_count += 1
                yield item

        # Also extract from top_sale_products
        top_products = data.get("top_sale_products", [])
        logger.info(
            f"Found {len(top_products)} top sale products for store {store_name}"
        )

        for product in top_products:
            item = self._extract_product_from_api(
                product, store_slug, store_name, store_id, category_lookup, scraped_at
            )
            if item:
                product_id = item.get("product_id")
                if product_id and product_id in self.scraped_product_ids:
                    continue
                if product_id:
                    self.scraped_product_ids.add(product_id)
                new_products_count += 1
                yield item

        logger.info(
            f"Scraped {new_products_count} new products from store {store_name}"
        )

        # Now request each leaf category page to get more products
        leaf_categories = self._get_leaf_categories_from_api(categories)
        logger.info(f"Found {len(leaf_categories)} leaf categories to scrape")

        for cat_info in leaf_categories:
            category_id = cat_info.get("category_id")
            category_slug = cat_info.get("slug")
            category_name = cat_info.get("name")
            category_path = cat_info.get("path", category_name)

            if not category_id or not category_slug:
                continue

            # Request category page with store context
            # URL pattern: /api/store/{store_slug}?category={category_id}
            # But this doesn't filter products, so try the category page URL pattern
            api_url = f"https://aeononlineshopping.com/api/store/{store_slug}?category={category_id}"

            yield scrapy.Request(
                api_url,
                callback=self.parse_category_page,
                meta={
                    "store_slug": store_slug,
                    "store_id": store_id,
                    "store_name": store_name,
                    "category_id": category_id,
                    "category_name": category_name,
                    "category_path": category_path,
                    "category_lookup": category_lookup,
                },
                headers={"Accept": "application/json"},
                dont_filter=True,
            )

    def _build_category_lookup(self, categories):
        """
        Build a lookup dict mapping category_id to category info.
        """
        lookup = {}

        def process_category(cat, parent_path=""):
            cat_data = cat.get("category", cat)
            cat_id = cat_data.get("category_id") or cat.get("category_id")

            content = cat_data.get("get_content", {})
            cat_name = content.get("name") or cat_data.get("name", "Unknown")

            current_path = f"{parent_path} > {cat_name}" if parent_path else cat_name

            if cat_id:
                lookup[cat_id] = {
                    "name": cat_name,
                    "path": current_path,
                    "slug": cat_data.get("slug"),
                }

            sub_cats = cat_data.get("sub_categories", [])
            for sub in sub_cats:
                process_category(sub, current_path)

        for cat in categories:
            process_category(cat)

        return lookup

    def _get_leaf_categories_from_api(self, categories):
        """
        Recursively extract leaf categories from API response.
        A leaf category has no sub_categories or empty sub_categories.
        """
        leaves = []

        def process_category(cat, parent_path=""):
            cat_data = cat.get("category", cat)
            cat_id = cat_data.get("category_id") or cat.get("category_id")

            content = cat_data.get("get_content", {})
            cat_name = content.get("name") or cat_data.get("name", "Unknown")

            current_path = f"{parent_path} > {cat_name}" if parent_path else cat_name

            sub_cats = cat_data.get("sub_categories", [])

            if not sub_cats:
                leaves.append(
                    {
                        "category_id": cat_id,
                        "name": cat_name,
                        "path": current_path,
                        "slug": cat_data.get("slug"),
                    }
                )
            else:
                for sub in sub_cats:
                    process_category(sub, current_path)

        for cat in categories:
            process_category(cat)

        return leaves

    def parse_category_page(self, response):
        """
        Parse category page API response to extract products.
        """
        store_slug = response.meta.get("store_slug")
        store_id = response.meta.get("store_id")
        store_name = response.meta.get("store_name")
        category_name = response.meta.get("category_name")
        category_path = response.meta.get("category_path")
        category_lookup = response.meta.get("category_lookup", {})

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON for category {category_name}")
            return

        products = data.get("products", [])

        if not products:
            return

        scraped_at = datetime.utcnow().isoformat()
        new_products_count = 0

        for product in products:
            item = self._extract_product_from_api(
                product,
                store_slug,
                store_name,
                store_id,
                category_lookup,
                scraped_at,
                category_name,
                category_path,
            )
            if item:
                product_id = item.get("product_id")
                if product_id and product_id in self.scraped_product_ids:
                    continue
                if product_id:
                    self.scraped_product_ids.add(product_id)
                new_products_count += 1
                yield item

        if new_products_count > 0:
            logger.info(
                f"Scraped {new_products_count} new products from category '{category_name}'"
            )

    def _extract_product_from_api(
        self,
        product,
        store_slug,
        store_name,
        store_id,
        category_lookup,
        scraped_at,
        override_category=None,
        override_path=None,
    ):
        """Extract product data from API response."""
        product_id = product.get("product_id")

        content = product.get("get_content", {})
        name = content.get("name") or product.get("name")

        price_detail = product.get("price_detail", {})
        price_khr = price_detail.get("price_in_khr")

        if not name:
            return None

        category_name = override_category or "Featured"

        slug = product.get("slug", "-")
        product_url = f"https://aeononlineshopping.com/product/{slug}/{product_id}?store_id={store_id}"

        return {
            "product_name": name,
            "category": category_name,
            "price": price_khr,
            "store": store_name,
            "store_slug": store_slug,
            "store_id": store_id,
            "currency": self.currency,
            "url": product_url,
            "scraped_at": scraped_at,
            "product_id": str(product_id),
        }
