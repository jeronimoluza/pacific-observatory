"""
Lesotho Virtual Mall — https://www.lesothovirtualmall.co.ls/.

DATA-QUALITY GOTCHA: the Store API's prices.currency_code field returns
"TMT" (Turkmenistan Manat's ISO code, a site misconfiguration) while
currency_symbol is "m" (Maloti) and the price scale matches real Lesotho
pricing. Force LSL rather than trusting currency_code from this API.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class VirtualmallLsSpider(WooBaseSpider):
    name = "virtualmall_ls"
    allowed_domains = ["lesothovirtualmall.co.ls", "www.lesothovirtualmall.co.ls"]
    currency = "LSL"
    language = "en"
    BASE_URL = "https://www.lesothovirtualmall.co.ls/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "LSL"
