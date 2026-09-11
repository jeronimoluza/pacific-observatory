"""
Oumbe Market (Cameroon) -- https://oumbemarket.com/.

Standard WooCommerce Store API on the versioned route. Wide supermarket/
grocery catalog (180 products, 9 pages of per_page=100 -- confirmed
disjoint page 1 vs page 2 product ids) covering water, cooking oil,
diapers, cleaning/toiletries etc. Contact/about text confirms this is a
Cameroon business (Douala/Yaounde mentioned repeatedly, no Cameroon phone
prefix found but no other country mentioned either).

CURRENCY GOTCHA: the Store API reports currency_code="USD" and the
rendered PDP genuinely displays a "$" symbol and USD-scale prices (e.g.
"eau minerale supermont 1.5L" at $0.49) -- verified live 2026-09-11 by
reading both the API payload and the rendered woocommerce-Price-amount
span, not just the API field (per the "read currency off the payload"
rule). This is unusual for a Cameroon storefront (XAF is the
countries.yaml default) but the site is internally consistent on USD
throughout, so USD is taken at face value rather than overridden.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class OumbemarketCmSpider(WooBaseSpider):
    name = "oumbemarket_cm"
    allowed_domains = ["oumbemarket.com"]
    currency = "USD"
    language = "fr"
    BASE_URL = "https://oumbemarket.com/wp-json/wc/store/v1/products"
