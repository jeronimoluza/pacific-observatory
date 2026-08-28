"""
Massy Stores Barbados — https://www.shopmassystoresbb.com/.

Default /wp-json/wc/store/v1/products path 500s on this install; the
?rest_route= query-string form of the REST route works instead.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MassyStoresBbSpider(WooBaseSpider):
    name = "massy_stores_bb"
    allowed_domains = ["shopmassystoresbb.com", "www.shopmassystoresbb.com"]
    currency = "BBD"
    language = "en"
    BASE_URL = "https://www.shopmassystoresbb.com/?rest_route=/wc/store/v1/products"
