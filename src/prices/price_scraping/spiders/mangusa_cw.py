"""
Mangusa Hypermarket (Curacao) — https://www.mangusahypermarket.com/.

Curacao's currency migrated from ANG to the new Caribbean Guilder (XCG); the
WooCommerce Store API already reflects the live code, so we trust
currency_code from the API rather than hardcoding.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MangusaCwSpider(WooBaseSpider):
    name = "mangusa_cw"
    allowed_domains = ["mangusahypermarket.com", "www.mangusahypermarket.com"]
    currency = "XCG"
    language = "en"
    BASE_URL = "https://www.mangusahypermarket.com/wp-json/wc/store/v1/products"
