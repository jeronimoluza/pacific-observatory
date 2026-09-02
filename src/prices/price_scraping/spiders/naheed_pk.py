"""
Naheed (Pakistan) -- https://www.naheed.pk/. A large general-merchandise
online retailer (Naheed Supermarket) on Magento 2, GraphQL open with no
auth. Confirmed live 2026-09-01.

Redirect trap: `naheed.pk` (bare, no `www`) 302-redirects to `www.naheed.pk`
and a POST body does not survive that redirect through curl_cffi/Scrapy's
downloader -- every POST to the bare domain came back
`{"errors":[{"message":"Syntax Error: Unexpected <EOF>"}]}` (an empty body
reaching the GraphQL parser), while the identical query against
`https://www.naheed.pk/graphql` returns real data. `GRAPHQL_URL`/`BASE_URL`
below both use the `www` host to avoid this.

Naheed's full root categoryList (id=2) spans ~20 top-level categories --
Groceries & Pets (5,304), Fresh St! Cafe (89), Pharmacy (2,439), Health &
Beauty (13,748), Phones & Computers, TV & Home Appliances, Women's/Men's
Fashion, Books, Home & Lifestyle, etc. Walking the whole thing would make
this read as a general department store (Health & Beauty and Fashion alone
dwarf groceries), and Pakistan already has three dept-store sources
(alfatah_pk, goto_pk, springs_pk) plus two pharmacy sources (hpharmacy_pk,
khasmart_pk). This spider is deliberately scoped to ONLY the two
grocery-led categories -- `Groceries & Pets` (id=46) and `Fresh St! Cafe`
(id=1079, a prepared/cafe-food section) -- so the source is honestly a
`channel: supermarket` food-and-beverage source, not a general marketplace
wearing a grocery disguise.

Prices come back as plain PKR integers via `price_range.minimum_price.
final_price.{value,currency}` (e.g. 1770, 435) -- the query's own
`currency` field is asserted "PKR", matching countries.yaml; no minor-unit
scaling needed.
"""

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider

_CATEGORY_IDS = ["46", "1079"]  # Groceries & Pets, Fresh St! Cafe


class NaheedPkSpider(MagentoGraphQLBaseSpider):
    name = "naheed_pk"
    allowed_domains = ["naheed.pk", "www.naheed.pk"]
    currency = "PKR"
    language = "en"

    GRAPHQL_URL = "https://www.naheed.pk/graphql"
    BASE_URL = "https://www.naheed.pk"
    ROOT_CATEGORY_ID = "2"

    async def start(self):
        for cat_id in _CATEGORY_IDS:
            yield self._page_request(cat_id, 1)
