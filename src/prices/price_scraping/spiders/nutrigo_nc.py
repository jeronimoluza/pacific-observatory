"""Spider for Nutrigo Nouvelle-Caledonie - https://www.nutrigo.nc/.

Nutrigo runs WooCommerce and exposes a public Store API. This scraper scopes
to the Alimentation saine category to keep the feed on nutrition/food products
rather than the full supplement and accessories catalogue.
"""

from ._woo_base import WooBaseSpider


class NutrigoNcSpider(WooBaseSpider):
    name = "nutrigo_nc"
    allowed_domains = ["nutrigo.nc", "www.nutrigo.nc"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://www.nutrigo.nc/wp-json/wc/store/v1/products"
    CATEGORY_ID = 527
