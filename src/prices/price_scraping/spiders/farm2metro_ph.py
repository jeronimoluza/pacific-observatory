"""Farm2Metro Philippines fresh-food Shopify collection feed."""

from __future__ import annotations

import logging

import scrapy

from ._shopify_base import MAX_PAGES, PER_PAGE, ShopifyBaseSpider

logger = logging.getLogger(__name__)


class Farm2MetroPhSpider(ShopifyBaseSpider):
    name = "farm2metro_ph"
    allowed_domains = ["pindotlang.com"]
    base_url = "https://pindotlang.com"
    currency = "PHP"
    language = "en"
    collection_paths = [
        "/collections/fresh-local-organic-vegetables/products.json",
        "/collections/fresh-meat-poultry/products.json",
        "/collections/fresh-eggs-selection/products.json",
        "/collections/fresh-seafoods/products.json",
    ]
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

    async def start(self):
        for path in self.collection_paths:
            yield scrapy.Request(
                f"{self.base_url}{path}?limit={PER_PAGE}&page=1",
                callback=self.parse_page,
                meta={"page": 1, "path": path},
            )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        products = data.get("products") if isinstance(data, dict) else None
        if not products:
            return
        page = response.meta["page"]
        path = response.meta["path"]
        logger.info(f"{self.name} path={path} page={page} count={len(products)}")
        for product in products:
            for item in self._items(product):
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            yield scrapy.Request(
                f"{self.base_url}{path}?limit={PER_PAGE}&page={page + 1}",
                callback=self.parse_page,
                meta={"page": page + 1, "path": path},
            )
