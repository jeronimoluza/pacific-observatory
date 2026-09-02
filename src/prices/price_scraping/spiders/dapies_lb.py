"""
Dapies (Lebanon) — https://dapies.com/. "Online Grocery Store in Lebanon |
Fresh & Healthy Groceries" — WooCommerce ("dapiesFood" theme).

Standard WooCommerce Store API, no auth. Confirmed live 2026-09-01:
currency_code=USD, currency_minor_unit=2 (e.g. price "450" -> $4.50,
matches the page's own price_html "4.50"). Sample: "Nabat Agar Agar Powder
100g" USD 4.50. Distinct storefront/company from spinneys_lb and
tripolimarket_lb (already onboarded) — not the same shelf.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DapiesLbSpider(WooBaseSpider):
    name = "dapies_lb"
    allowed_domains = ["dapies.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://dapies.com/wp-json/wc/store/v1/products"
