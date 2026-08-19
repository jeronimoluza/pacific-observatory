"""
Spider for Gorilla Pets (India) — https://gorillapets.com/.

WooCommerce Store API confirmed live 2026-08-18: GET
/wp-json/wc/store/v1/products?per_page=100&page=N -> 200, INR minor-unit
JSON prices (currency_minor_unit=2). Pet food and supplies (Acana, Bio-Groom,
etc.), sample "Acana Adult Indoor Sterilized Cat Dry Food..." INR 2430.00
(sale_price on a 269900/243000 regular/sale pair).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class GorillapetsInSpider(WooBaseSpider):
    name = "gorillapets_in"
    allowed_domains = ["gorillapets.com"]
    currency = "INR"
    language = "en"
    BASE_URL = "https://gorillapets.com/wp-json/wc/store/v1/products"
