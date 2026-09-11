"""
Budget Shoppen (Suriname) -- https://budgetshoppen.com/.

Standard WooCommerce Store API. TVs, appliances, electronics (e.g.
'Scote 60-100 Inch Mobile TV Floor Stand with Shelf') -- classified
electronics.

Verified live 2026-09-11: x-wp-total=1483, x-wp-totalpages=1483 at
per_page=1 (i.e. ~1,483 products, ~75 pages at per_page=20). Page 1 vs
page 2 (per_page=20) returned disjoint product-id sets, zero overlap --
genuine pagination.

Currency: Store API reports currency_code=SRD consistently -- matches
Suriname's country currency. currency_minor_unit=0 (integer SRD, no
decimal shift). 2 of 40 sampled products carry a "0" price
(price-on-application placeholders); the base class already drops
zero-price rows.

Page family: API (Store API JSON; permalinks are real PDP URLs but never
fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class BudgetshoppenSrSpider(WooBaseSpider):
    name = "budgetshoppen_sr"
    allowed_domains = ["budgetshoppen.com", "www.budgetshoppen.com"]
    currency = "SRD"
    language = "nl"
    BASE_URL = "https://budgetshoppen.com/wp-json/wc/store/v1/products"
