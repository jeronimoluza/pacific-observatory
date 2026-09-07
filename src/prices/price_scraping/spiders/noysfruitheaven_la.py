"""Spider for Noy's Fruit Heaven (Lao PDR)."""

from ._woo_base import WooBaseSpider


class NoysFruitHeavenLaSpider(WooBaseSpider):
    name = "noysfruitheaven_la"
    allowed_domains = ["noysfruitheaven.com", "www.noysfruitheaven.com"]
    currency = "LAK"
    language = "en"
    BASE_URL = "https://noysfruitheaven.com/wp-json/wc/store/v1/products"
