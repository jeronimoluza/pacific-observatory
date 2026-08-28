"""
Khasmart (Pakistan) — https://khasmart.pk/.

Pharmacy retailer (medicine, personal care) with a smaller grocery/baby-shop
section mixed in.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class KhasmartPkSpider(WooBaseSpider):
    name = "khasmart_pk"
    allowed_domains = ["khasmart.pk"]
    currency = "PKR"
    language = "en"
    BASE_URL = "https://khasmart.pk/wp-json/wc/store/v1/products"
