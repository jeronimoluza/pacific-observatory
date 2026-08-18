"""
H Pharmacy (Pakistan) — https://hpharmacy.pk/.

Pharmacy + personal-care retailer.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class HpharmacyPkSpider(WooBaseSpider):
    name = "hpharmacy_pk"
    allowed_domains = ["hpharmacy.pk"]
    currency = "PKR"
    language = "en"
    BASE_URL = "https://hpharmacy.pk/wp-json/wc/store/v1/products"
