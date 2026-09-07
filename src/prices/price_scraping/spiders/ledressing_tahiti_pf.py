"""Le Dressing Tahiti apparel WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class LeDressingTahitiPfSpider(WooBaseSpider):
    name = "ledressing_tahiti_pf"
    allowed_domains = ["ledressingtahiti.com"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://ledressingtahiti.com/wp-json/wc/store/v1/products"
