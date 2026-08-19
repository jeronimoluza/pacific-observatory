"""
Spider for Carrefour Tunisia — https://www.carrefour.tn/.

Magento 2 storefront (distinct backend/operator from Carrefour Egypt's
MAF/Akamai stack — no WAF here). Homepage is a tiny SPA shell but /graphql
is open with no auth. categoryList under the default root (id=2) exposes
the full hypermarket taxonomy (Le marché, Épicerie Salée/Sucrée, Crèmerie,
Surgelés, Boissons, etc.).
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class CarrefourTnSpider(MagentoGraphQLBaseSpider):
    name = "carrefour_tn"
    allowed_domains = ["carrefour.tn"]
    currency = "TND"
    language = "fr"

    GRAPHQL_URL = "https://www.carrefour.tn/graphql"
    BASE_URL = "https://www.carrefour.tn"
    ROOT_CATEGORY_ID = "2"
