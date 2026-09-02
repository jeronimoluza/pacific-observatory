"""La Cave de Tahiti (French Polynesia) -- WooCommerce Store API."""

from ._woo_base import WooBaseSpider


class LaCaveDeTahitiPfSpider(WooBaseSpider):
    name = "lacavedetahiti_pf"
    allowed_domains = ["lacavedetahiti.pf"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://lacavedetahiti.pf/wp-json/wc/store/v1/products"
    CATEGORY_ID = 478
