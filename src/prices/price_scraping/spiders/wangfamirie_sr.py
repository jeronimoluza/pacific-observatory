"""
Wangfamirie (Suriname) -- https://wangfamirie.com/

"Boodschappen en Paketten voor Suriname" -- a Dutch-language diaspora
grocery/parcel service: order online (EUR-priced) and have it delivered to
family in Suriname. Found via a Dutch-language ddgs search ("supermarkt
online bestellen Paramaribo Suriname boodschappen"), probed 2026-09-11.
WooCommerce Store API confirmed live, open, no auth
(/wp-json/wc/store/v1/products). X-WP-Total: 3,601 across 181 pages.
Enumerability confirmed: page1 vs page2 ids disjoint.

Distinct business/catalog from the existing avoda_sr (and its now2su.com
sibling shelf): a page-5 name-overlap check against avoda_sr's page 5
found 0/30 matching product names, and the category taxonomy is a
completely different naming convention (Dutch grocery-department names
rather than avoda's English department names) -- not a duplicate shelf.

Rich, food-heavy category structure (product counts as of 2026-09-11):
DRANKEN (drinks) 211, Family packs 572, FRUIT 22, GROENTEN (vegetables)
75, Kip (chicken) 46, ONTBIJT (breakfast) 203, Rund (beef) 22, SAUS EN
MARINADE 195, THEE & KOFFIE 49, VIS (fish) 32, VLEES (meat) 154, Varken
(pork) 42, ZOET & SNACKS 156, ZUIVEL (dairy) 95, Zoutvlees (salted meat)
10, BROOD (bread) 14, Beleg (spreads) 21, DIEPVRIES (frozen) 21, KRUIDEN
(spices) 30 -- alongside non-food departments (BABY, PHARMA, SCHOOL,
HYGIENE, TOILETARTIKELEN, ELEKTRO, DAMES).

currency_code=EUR from the API (this is a diaspora order-and-deliver
model, not domestically SRD-priced retail, same pattern already
documented for now2su.com) -- kept as reported by the API rather than
force-overridden, consistent with the "site's own currency code wins"
rule. Analysts should be aware this reflects diaspora-order pricing, not
Suriname's domestic SRD retail price level, when interpreting PPP output
for this source.

Page family: API (reads the JSON Store API directly, never fetches a
rendered page).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class WangfamirieSrSpider(WooBaseSpider):
    name = "wangfamirie_sr"
    allowed_domains = ["wangfamirie.com"]
    currency = "EUR"
    language = "nl"
    BASE_URL = "https://wangfamirie.com/wp-json/wc/store/v1/products"
