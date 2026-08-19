"""
Spider for Van den Tweel Supermarket (Curaçao) — https://shopvdtcuracao.com/.

Magento 2 storefront, open GraphQL at /graphql, no auth. categoryList under
the default root (id=2) has a single child department ("Producten",
~1,800 products) covering the whole catalog.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class VandentweelCwSpider(MagentoGraphQLBaseSpider):
    name = "vandentweel_cw"
    allowed_domains = ["shopvdtcuracao.com"]
    currency = "ANG"
    language = "nl"

    GRAPHQL_URL = "https://shopvdtcuracao.com/graphql"
    BASE_URL = "https://shopvdtcuracao.com"
    ROOT_CATEGORY_ID = "2"
