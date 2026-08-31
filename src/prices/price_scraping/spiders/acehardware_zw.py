"""
Ace Hardware Zimbabwe — https://acehardware.co.zw/.

Standard WooCommerce Store API. USD prices at currency_minor_unit=2
(e.g. price "2500" -> $25.00), confirmed against the site's own
price_html on the same row. Hardware/tools/building-materials catalog,
distinct COICOP division from the existing supermarket sources.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class AcehardwareZwSpider(WooBaseSpider):
    name = "acehardware_zw"
    allowed_domains = ["acehardware.co.zw"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://acehardware.co.zw/wp-json/wc/store/v1/products"
