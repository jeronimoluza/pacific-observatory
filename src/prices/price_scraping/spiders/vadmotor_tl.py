"""Spider for VAD Motor (Timor-Leste)."""

from ._woo_base import WooBaseSpider


class VadmotorTlSpider(WooBaseSpider):
    name = "vadmotor_tl"
    allowed_domains = ["vadmotor.com", "www.vadmotor.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://vadmotor.com/wp-json/wc/store/v1/products"
