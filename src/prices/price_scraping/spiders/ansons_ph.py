"""Anson's Philippines appliances and electronics WooCommerce Store API."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class AnsonsPhSpider(WooBaseSpider):
    name = "ansons_ph"
    allowed_domains = ["ansons.ph"]
    BASE_URL = "https://ansons.ph/wp-json/wc/store/v1/products"
    currency = "PHP"
    language = "en"
    custom_settings = {**WooBaseSpider.custom_settings, "COOKIES_ENABLED": False}
