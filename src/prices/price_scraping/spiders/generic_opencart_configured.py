"""Configurable OpenCart category crawler for generated manifests."""

from ._opencart_base import OpencartBaseSpider


class GenericOpencartConfiguredSpider(OpencartBaseSpider):
    name = "generic_opencart_configured"

    def __init__(self, source_label=None, category_urls=None, nav_url=None, currency=None, language="en", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if source_label:
            self.source_label = source_label
        self.CATEGORY_URLS = tuple(category_urls or [])
        self.NAV_URL = nav_url or ""
        self.currency = currency or self.currency
        self.language = language or self.language
        domains = []
        for url in list(self.CATEGORY_URLS) + ([self.NAV_URL] if self.NAV_URL else []):
            if "//" in url:
                domains.append(url.split("//", 1)[-1].split("/", 1)[0].replace("www.", ""))
        self.allowed_domains = sorted(set(domains))
