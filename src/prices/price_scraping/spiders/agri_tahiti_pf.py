"""Agri Tahiti garden, agriculture, and hardware WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class AgriTahitiPfSpider(WooBaseSpider):
    name = "agri_tahiti_pf"
    allowed_domains = ["agt.pf"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://agt.pf/wp-json/wc/store/v1/products"
