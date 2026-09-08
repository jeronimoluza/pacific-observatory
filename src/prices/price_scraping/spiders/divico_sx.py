"""
DIVICO Cash & Carry (Sint Maarten) -- https://www.divico.shop/.

Vanilla Shopify storefront; /products.json?limit=250&page=N confirmed live
2026-09-05 (curl_cffi chrome124): 3,000 products across 12 full pages, page
N and N+1 fully disjoint, terminating cleanly on an empty page.

Locality: the store's own meta description reads "DIVICO Cash & Carry is
your one-stop spot for all your grocery, household and children's products
at wholesale prices. Located in the island of Sint Maarten"; the operator
publishes a Sint Maarten phone number (+1-721-544-3003) and delivers across
Cole Bay, Simpson Bay, Philipsburg, Cupecoy and Mullet Bay. This is
in-country shelf pricing, not a diaspora shipper.

Currency: Shopify.currency on the storefront reports {"active":"USD"},
so USD -- NOT the ANG in countries.yaml. Sint Maarten is heavily
dollarised and this tenant prices in USD; the sibling source `costuless_sx`
records ANG because that platform renders the guilder symbol, so the two
are genuinely different price displays, not an inconsistency to "fix".

Catalogue is cash-and-carry pack sizes (e.g. "S.Pellegrino PET Bottle 24 /
50CL", "HAM PICNICS SMOKED PORK SHOULDER / KG") alongside single units --
hence `channel: wholesale`, not supermarket. Shopify `product_type` is
almost entirely the tenant's internal "Staging"/"staging" label rather than
a real taxonomy, so `category` carries little signal here; product names are
real and are what the classifier reads.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class DivicoSxSpider(ShopifyBaseSpider):
    name = "divico_sx"
    allowed_domains = ["divico.shop", "www.divico.shop"]
    base_url = "https://www.divico.shop"
    currency = "USD"
    language = "en"
