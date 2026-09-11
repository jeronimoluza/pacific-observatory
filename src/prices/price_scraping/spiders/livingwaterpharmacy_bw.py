"""Living Water Pharmacy -- https://livingwaterpharmacy.com/.

Standard WooCommerce Store API. Probed 2026-09-11: 33 products total
(one page at per_page=100), pharmacy catalog (syrups, supplements --
Emex Syrup, Osteocare, etc). currency_code=BWP, minor_unit=2, matches
countries.yaml despite the .com TLD (site is a Gaborone pharmacy, not a
US/generic storefront). Pagination verified distinct at per_page=5:
page1 ids {328,329,330,331,332} vs page2 ids {323,324,325,326,327}, zero
overlap.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class LivingwaterpharmacyBwSpider(WooBaseSpider):
    name = "livingwaterpharmacy_bw"
    allowed_domains = ["livingwaterpharmacy.com"]
    currency = "BWP"
    language = "en"
    BASE_URL = "https://livingwaterpharmacy.com/wp-json/wc/store/v1/products"
