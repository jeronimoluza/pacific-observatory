"""
Ashgabatmarket (Turkmenistan) — https://ashgabatmarket.com/.

Standard WooCommerce Store API. Wide electronics/gadgets/appliances
catalog (~7,244 products per X-WP-Total) with TMT prices at
currency_minor_unit=2 (minor units, e.g. 92000000 -> 920000.00 TMT).
Site is hosted outside Turkmenistan (5.63.156.22, non-.tm IP space),
unlike most Turkmen-registered domains which are hosted on
Turkmentelecom's own network (216.250.x.x / 95.85.x.x) and refuse
external TCP connections outright.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class AshgabatmarketTmSpider(WooBaseSpider):
    name = "ashgabatmarket_tm"
    allowed_domains = ["ashgabatmarket.com"]
    currency = "TMT"
    language = "ru"
    BASE_URL = "https://ashgabatmarket.com/wp-json/wc/store/v1/products"
