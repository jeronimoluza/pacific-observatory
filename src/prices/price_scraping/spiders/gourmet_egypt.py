"""
Spider for Gourmet Egypt (Egypt) — https://gourmetegypt.com/.

Magento 2 storefront with an open GraphQL endpoint at /graphql (no auth
required; the REST /rest/V1/products surface 401s). categoryList under the
default root category (id=2) enumerates the full department taxonomy
(Meat/Poultry/Seafood, Bakery, Dairy & Eggs, Fruits & Vegetables, Frozen,
Food Cupboard, Beverages, etc.); we walk each leaf category's products.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class GourmetEgyptSpider(MagentoGraphQLBaseSpider):
    name = "gourmet_egypt"
    allowed_domains = ["gourmetegypt.com"]
    currency = "EGP"
    language = "en"

    GRAPHQL_URL = "https://gourmetegypt.com/graphql"
    BASE_URL = "https://gourmetegypt.com"
    ROOT_CATEGORY_ID = "2"
