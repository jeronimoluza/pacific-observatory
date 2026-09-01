"""Rice2MeatU (Saipan, Northern Mariana Islands) -- WooCommerce Store API."""

from ._woo_base import WooBaseSpider


class Rice2MeatUMpSpider(WooBaseSpider):
    name = "rice2meatu_mp"
    allowed_domains = ["rice2meatu.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://rice2meatu.com/wp-json/wc/store/v1/products"
