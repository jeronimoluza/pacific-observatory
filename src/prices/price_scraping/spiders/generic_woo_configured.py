"""Configurable WooCommerce Store API crawler for generated manifests."""

from ._woo_base import WooBaseSpider


class GenericWooConfiguredSpider(WooBaseSpider):
    name = "generic_woo_configured"

    def __init__(self, source_label=None, api_url=None, base_url=None, currency=None, language="en", category_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if source_label:
            self.source_label = source_label
        self.BASE_URL = (api_url or base_url or self.BASE_URL or "").rstrip("/")
        self.currency = currency or self.currency
        self.language = language or self.language
        self.CATEGORY_ID = category_id
