"""
DETO Handelmaatschappij (Suriname) -- https://deto.sr/.

Standard WooCommerce Store API. Hardware/tools/household goods (e.g.
'ARTPLAST TOOLBOX PP M/WIELEN LINEA TEKNA 46X28X66.5CM') -- classified
home-improvement.

Verified live 2026-09-11: x-wp-total=884, x-wp-totalpages=884 at
per_page=1 (i.e. 884 products, ~45 pages at per_page=20). Page 1 vs page
2 (per_page=20) returned disjoint product-id sets, zero overlap --
genuine pagination.

Currency: Store API's currency_code field returns "ABC", NOT a real
ISO 4217 code -- a tenant misconfiguration, not a real currency (per the
wave-5 brief's flag). currency_symbol/currency_prefix on the same
response both say "SRD", and this was cross-checked against a live
rendered product page (https://www.deto.sr/product/artplast-toolbox-pp-m
-wielen-linea-tekna-46x28x66-5cm/ 2026-09-11): the page's own
woocommerce-Price-amount markup shows "SRD 2.741,04", which matches
274104 / 10**2 computed from the API's own price + currency_minor_unit.
So the underlying price math is correct and only the currency_code label
is bogus. FORCE_CURRENCY="SRD" pins the real currency instead of
propagating the "ABC" placeholder.

Note: permalinks resolve on www.deto.sr (the bare domain also serves the
Store API directly).

Page family: API (Store API JSON; permalinks are real PDP URLs but never
fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DetoSrSpider(WooBaseSpider):
    name = "deto_sr"
    allowed_domains = ["deto.sr", "www.deto.sr"]
    currency = "SRD"
    language = "nl"
    BASE_URL = "https://deto.sr/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "SRD"
