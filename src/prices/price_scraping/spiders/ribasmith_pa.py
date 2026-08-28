"""
Spider for Riba Smith (Panama) — https://www.ribasmith.com/.

Magento 2 storefront, open GraphQL at /graphql, no auth. categoryList's
children under the default root (id=2) are thin marketing/nav categories
(promotions, seasonal campaigns) that sum to a small fraction of the real
catalog; products(filter:{category_id:{eq:"2"}}) directly returns the full
flat catalog instead (10000 on a single unpaged probe, likely the
Elasticsearch max_result_window rather than the true count), so this
walks the root id directly rather than categoryList children.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class RibasmithPaSpider(MagentoGraphQLBaseSpider):
    name = "ribasmith_pa"
    allowed_domains = ["ribasmith.com"]
    currency = "USD"
    language = "es"

    GRAPHQL_URL = "https://www.ribasmith.com/graphql"
    BASE_URL = "https://www.ribasmith.com"
    ROOT_CATEGORY_ID = "2"
    WALK_ROOT_DIRECTLY = True
