"""
Bobby's Marketplace (British Virgin Islands) -- https://bobbysmarketplacevi.com/.

Road Town, Tortola grocery / provisioning / household store (site footer:
"The British Virgin Islands' favorite stop for groceries, provisioning").
Standard WooCommerce Store API, no auth; currency_minor_unit=2, USD.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class BobbysmarketplaceVgSpider(WooBaseSpider):
    name = "bobbysmarketplace_vg"
    allowed_domains = ["bobbysmarketplacevi.com"]
    currency = "USD"
    language = "en"
    FORCE_CURRENCY = "USD"
    BASE_URL = "https://bobbysmarketplacevi.com/wp-json/wc/store/v1/products"
