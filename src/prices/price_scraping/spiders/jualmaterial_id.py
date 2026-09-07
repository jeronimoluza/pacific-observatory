"""JualMaterial Indonesia hardware and building materials WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class JualmaterialIdSpider(WooBaseSpider):
    name = "jualmaterial_id"
    allowed_domains = ["www.jualmaterial.com", "jualmaterial.com"]
    BASE_URL = "https://www.jualmaterial.com/wp-json/wc/store/v1/products"
    currency = "IDR"
    language = "id"
    custom_settings = {**WooBaseSpider.custom_settings, "COOKIES_ENABLED": False}
