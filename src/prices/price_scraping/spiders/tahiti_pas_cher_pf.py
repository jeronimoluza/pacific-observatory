"""Tahiti Pas Cher furniture and household goods WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class TahitiPasCherPfSpider(WooBaseSpider):
    name = "tahiti_pas_cher_pf"
    allowed_domains = ["www.tahitipascher.pf", "tahitipascher.pf"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://www.tahitipascher.pf/wp-json/wc/store/v1/products"
