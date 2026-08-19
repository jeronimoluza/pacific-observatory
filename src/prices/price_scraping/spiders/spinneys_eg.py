"""
Spider for Spinneys Egypt — https://spinneys-egypt.com/.

Nuxt SPA fronting Magento 2, same mcprod.<domain>/graphql backend pattern as
Hyper One and Seoudi Market (the storefront's own /graphql proxy 400s on a
raw POST body; use the mcprod subdomain directly).
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class SpinneysEgSpider(MagentoGraphQLBaseSpider):
    name = "spinneys_eg"
    allowed_domains = ["spinneys-egypt.com", "mcprod.spinneys-egypt.com"]
    currency = "EGP"
    language = "en"

    GRAPHQL_URL = "https://mcprod.spinneys-egypt.com/graphql"
    BASE_URL = "https://spinneys-egypt.com"
    ROOT_CATEGORY_ID = "2"
