"""
eKissaan (Pakistan) — https://ekissaan.com/.

Direct-from-farm dry fruit / preserves / oils shop; whole catalog is food.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class EkissaanPkSpider(WooBaseSpider):
    name = "ekissaan_pk"
    allowed_domains = ["ekissaan.com"]
    currency = "PKR"
    language = "en"
    BASE_URL = "https://ekissaan.com/wp-json/wc/store/v1/products"
