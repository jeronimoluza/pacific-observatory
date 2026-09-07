"""Spider for Kulo Home (Timor-Leste)."""

from ._woo_base import WooBaseSpider


class KulohomeTlSpider(WooBaseSpider):
    name = "kulohome_tl"
    allowed_domains = ["kulohome.com", "www.kulohome.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://kulohome.com/wp-json/wc/store/v1/products"
