"""
Tech Wiz Pro Eswatini - shop.twpsz.com.

Standard WooCommerce Store API. SZL prices at currency_minor_unit=2.
Small catalog (~38 products confirmed by walking to an empty page) but
genuinely diverse: smartphones, home appliances, audio, books, garden,
health & beauty, sports & travel -- good breadth for its size.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TwpszSzSpider(WooBaseSpider):
    name = "twpsz_sz"
    allowed_domains = ["shop.twpsz.com"]
    currency = "SZL"
    language = "en"
    BASE_URL = "https://shop.twpsz.com/wp-json/wc/store/v1/products"
