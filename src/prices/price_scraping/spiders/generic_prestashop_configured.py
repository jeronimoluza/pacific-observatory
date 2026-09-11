"""Configurable PrestaShop catalog crawler for generated manifests."""

from ._prestashop_base import PrestashopBaseSpider


class GenericPrestashopConfiguredSpider(PrestashopBaseSpider):
    name = "generic_prestashop_configured"

    def __init__(self, source_label=None, home_url=None, currency=None, language="en", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if source_label:
            self.source_label = source_label
        self.HOME_URL = (home_url or self.HOME_URL or "").rstrip("/") + "/"
        self.currency = currency or self.currency
        self.language = language or self.language
        domain = self.HOME_URL.split("//", 1)[-1].split("/", 1)[0].replace("www.", "")
        self.allowed_domains = [domain] if domain else []
