"""GNC Guam WooCommerce storefront."""

from ._woo_base import WooBaseSpider


class GncGuamSpider(WooBaseSpider):
    name = "gnc_guam"
    allowed_domains = ["gncguam.com", "www.gncguam.com"]
    BASE_URL = "https://gncguam.com/wp-json/wc/store/v1/products"
    currency = "USD"
    language = "en"
