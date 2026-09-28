"""
Zudua Shopping (Tanzania) — https://zudua.co.tz/.

Standard WooCommerce Store API. TZS prices at currency_minor_unit=0 (no
scaling needed — confirmed via /wp-json/wc/store/v1/products, prices
field: {"price": "8900000", "currency_code": "TZS", "currency_minor_unit":
0}). Cross-division general online store: fashion, electronics, home
essentials and school supplies per the site's own description — dept-store
channel, distinct COICOP divisions from the existing food-heavy Tanzania
sources (fastandfresh_tz, nidadanish_tz, wfp_prices).

Verified live 2026-09-28: GET /wp-json/wc/store/v1/products?per_page=5 ->
200, x-wp-total header 1997, real TZS-priced electronics ("iPhone Duo
512GB" 8,900,000 TZS, "APC 800VA EASY UPS BATTERY BACKUP" 270,000 TZS).
Page 2 returns a fully distinct set, confirming enumeration.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ZuduaTzSpider(WooBaseSpider):
    name = "zudua_tz"
    allowed_domains = ["zudua.co.tz"]
    currency = "TZS"
    language = "en"
    BASE_URL = "https://zudua.co.tz/wp-json/wc/store/v1/products"
