"""
Hubbards Food Fair (Grenada) -- https://foodfair.gd/.

Magento 2 storefront. GraphQL is open and authoritative for this tenant
(verified live: root category id "2" -> 16 real grocery child categories --
Baby Food & Products, Beverages, Breakfast Products, Candy & Snacks,
Condiments, ... -- summing to ~2,188 products). Prices report currency
"XCD" directly in price_range.minimum_price.final_price.currency, matching
Grenada's own currency.

Enumerability confirmed: products(category_id=296 "Beverages") page 1 vs
page 2 (pageSize=10) returned 0 SKU overlap.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class FoodfairGdSpider(MagentoGraphQLBaseSpider):
    name = "foodfair_gd"
    allowed_domains = ["foodfair.gd"]
    currency = "XCD"
    language = "en"
    GRAPHQL_URL = "https://foodfair.gd/graphql"
    BASE_URL = "https://foodfair.gd"
    ROOT_CATEGORY_ID = "2"
