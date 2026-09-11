"""
CTM Botswana (tiles, taps, bathrooms) - ctm.co.bw.

Magento 2 (Adobe Commerce) GraphQL at /graphql, shared across CTM's
country storefronts. Critical gotcha: without a Store header the endpoint
resolves to the KE (Kenya) store view -- storeConfig{store_code} returns
"KE"/"CTM Kenya"/base_currency_code "KES" on a bare request to
https://ctm.co.bw/graphql. Passing header Store: BW resolves correctly to
store_code "BW", store_name "CTM Botswana", base_currency_code "BWP".
Every request below carries that header; omitting it would silently write
Kenyan-store rows under a Botswana source_key.

Overrides MagentoGraphQLBaseSpider's category-tree walk with a single
unfiltered products(filter:{}) paginated query, since the plain query
already returns the full catalog (total_count 1097) without needing to
discover category ids first -- simpler and avoids the base's documented
thin-categoryList undercount risk.

Probed 2026-09-11: page 1 vs page 2 (pageSize=20, Store: BW) returned 20
distinct product SKUs each; prices are BWP tile/bathroom-fixture prices in
whole currency units (e.g. E287.86 -> value 287.86, no minor-unit scaling
needed on this GraphQL surface, unlike WooCommerce's Store API).
"""

import json
import logging

import scrapy

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider

logger = logging.getLogger(__name__)

_PRODUCTS_QUERY = (
    "{ products(filter: {}, pageSize: %d, currentPage: %d) {"
    " total_count items { sku name url_key"
    " price_range { minimum_price { final_price { value currency } } } } } }"
)


class CtmBwSpider(MagentoGraphQLBaseSpider):
    name = "ctm_bw"
    allowed_domains = ["ctm.co.bw"]
    currency = "BWP"
    language = "en"
    GRAPHQL_URL = "https://ctm.co.bw/graphql"
    BASE_URL = "https://ctm.co.bw"
    PAGE_SIZE = 100

    async def start(self):
        yield self._page_request("", 1)

    def _page_request(self, category_id, page):
        return scrapy.Request(
            self.GRAPHQL_URL,
            method="POST",
            headers={"Content-Type": "application/json", "Store": "BW"},
            body=json.dumps(
                {"query": _PRODUCTS_QUERY % (self.PAGE_SIZE, page)}
            ),
            callback=self.parse_page,
            meta={"category_id": category_id, "page": page},
        )
