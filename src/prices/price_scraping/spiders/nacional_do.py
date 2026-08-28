"""
Spider for Supermercados Nacional (Dominican Republic) —
https://www.supermercadosnacional.com/.

Magento 2 storefront, open GraphQL at /graphql, no auth. categoryList under
the default root (id=2) exposes the full chain taxonomy (Carnes/Pescados,
Frutas y Vegetales, Lácteos y Huevos, Despensa, Bebidas, etc.).
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class NacionalDoSpider(MagentoGraphQLBaseSpider):
    name = "nacional_do"
    allowed_domains = ["supermercadosnacional.com"]
    currency = "DOP"
    language = "es"

    GRAPHQL_URL = "https://www.supermercadosnacional.com/graphql"
    BASE_URL = "https://www.supermercadosnacional.com"
    ROOT_CATEGORY_ID = "2"
