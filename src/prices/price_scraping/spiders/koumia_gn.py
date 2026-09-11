"""
Koumia marketplace (Guinea) -- https://koumia.com/.

Shopify storefront. /products.json is open and unauthenticated. Currency
confirmed as GNF from the storefront's own shop-capabilities JSON
(`"currencyCode":"GNF"` embedded in the rendered page, shopId 98117255510)
-- the /products.json payload itself carries no currency field, so this is
pinned at the spider level per _shopify_base's contract.

Catalog: 114 products total (limit=250 page 1 returns all 114; page 2
empty). Enumerability confirmed at limit=50: page 1 vs page 2, 0 id
overlap. Small-appliance/houseware marketplace (kettles, water dispensers,
pressure washers, coffee machines, meat grinders, ...).

channel: marketplace per the skill's marketplace-catalog rule.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class KoumiaGnSpider(ShopifyBaseSpider):
    name = "koumia_gn"
    allowed_domains = ["koumia.com"]
    base_url = "https://koumia.com"
    currency = "GNF"
    language = "fr"
