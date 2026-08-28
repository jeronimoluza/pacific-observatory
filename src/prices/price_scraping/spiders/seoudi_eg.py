"""
Spider for Seoudi Market (Egypt) — https://seoudisupermarket.com/.

Nuxt SPA fronting Magento 2, same mcprod.<domain>/graphql backend pattern as
Hyper One and Spinneys Egypt. The root category (id=2) itself carries zero
directly-assigned products here — categoryList must be walked one level
into its children (Fruits & Vegetables, Dairy/Eggs/Cheese, Bakery, Frozen,
Hot Drinks, etc.) to reach any products at all.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class SeoudiEgSpider(MagentoGraphQLBaseSpider):
    name = "seoudi_eg"
    allowed_domains = ["seoudisupermarket.com", "mcprod.seoudisupermarket.com"]
    currency = "EGP"
    language = "en"

    GRAPHQL_URL = "https://mcprod.seoudisupermarket.com/graphql"
    BASE_URL = "https://seoudisupermarket.com"
    ROOT_CATEGORY_ID = "2"
