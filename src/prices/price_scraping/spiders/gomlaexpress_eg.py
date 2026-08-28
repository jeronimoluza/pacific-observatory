"""
Spider for Gomla Express (Egypt) — https://gomlaexpress.com/.

WooCommerce Store API confirmed live 2026-08-18: GET
/wp-json/wc/store/v1/products?per_page=100&page=N -> 200, EGP JSON prices
(currency_minor_unit=0 -- prices are whole EGP, no division needed). Broad
first-party catalog: shoes/bags, home textiles, cleaning supplies, packaging
materials and a "Gomla Go" wholesale line, plus smaller food categories
(dates, spices, frozen vegetables, cheese, ice cream). Product names are
Arabic.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class GomlaexpressEgSpider(WooBaseSpider):
    name = "gomlaexpress_eg"
    allowed_domains = ["gomlaexpress.com"]
    currency = "EGP"
    language = "ar"
    BASE_URL = "https://gomlaexpress.com/wp-json/wc/store/v1/products"
