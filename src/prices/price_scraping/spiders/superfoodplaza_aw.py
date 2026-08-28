"""Super Food Plaza (Aruba) -- https://shop.superfoodaruba.com/. Round 3
platform-fingerprint reversal: prior round dropped this as brochure-only
WordPress; the storefront actually runs the NCR Freshop hosted catalog
(app_key=super_food_plaza_aruba, store_id=4592, verified live via
/2/stores). 11,254-item full-line grocery/household/personal-care catalog,
price symbol ``ƒ`` confirms AWG (Aruban florin) matching countries.yaml.
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class SuperfoodplazaAwSpider(FreshopBaseSpider):
    name = "superfoodplaza_aw"
    currency = "AWG"
    language = "en"

    APP_KEY = "super_food_plaza_aruba"
    STORE_ID = "4592"
