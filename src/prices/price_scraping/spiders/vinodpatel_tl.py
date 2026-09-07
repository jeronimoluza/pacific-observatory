"""Spider for Vinod Patel Timor-Leste."""

from ._woo_base import WooBaseSpider


class VinodpatelTlSpider(WooBaseSpider):
    name = "vinodpatel_tl"
    allowed_domains = ["vinodpatel.tl", "www.vinodpatel.tl"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://www.vinodpatel.tl/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "USD"
    custom_settings = WooBaseSpider.custom_settings | {"CLOSESPIDER_ITEMCOUNT": 1000}
