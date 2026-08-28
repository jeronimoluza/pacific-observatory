"""
Spider for Hyper One (Egypt) — https://www.hyperone.com.eg/.

Nuxt SPA fronting Magento 2. The storefront's own /graphql proxy 400s on a
raw POST body; the underlying backend at https://mcprod.hyperone.com.eg/graphql
(discovered via window.__NUXT__.config.apiUrl) accepts the same queries
directly with no auth.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class HyperoneEgSpider(MagentoGraphQLBaseSpider):
    name = "hyperone_eg"
    allowed_domains = ["hyperone.com.eg", "mcprod.hyperone.com.eg"]
    currency = "EGP"
    language = "en"

    GRAPHQL_URL = "https://mcprod.hyperone.com.eg/graphql"
    BASE_URL = "https://www.hyperone.com.eg"
    ROOT_CATEGORY_ID = "2"
