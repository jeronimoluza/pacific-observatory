"""
Z-Store (Zimbabwe) — https://zstore.co.zw/.

Standard WooCommerce Store API. USD prices at currency_minor_unit=2
(e.g. price "11500" -> $115.00). Liquor/spirits/wine specialty retailer,
221 products (X-WP-Total header), zero rows with a $0 price (checked the
full catalog) — cleaner than reeltecelectronics.co.zw, which was parked
for having 81% $0 "price on application" rows.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ZstoreZwSpider(WooBaseSpider):
    name = "zstore_zw"
    allowed_domains = ["zstore.co.zw"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://zstore.co.zw/wp-json/wc/store/v1/products"
