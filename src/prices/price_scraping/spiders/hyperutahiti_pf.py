"""Hyper U Tahiti (French Polynesia) -- https://www.hyperutahiti.com/. Click &
collect / delivery storefront for the Hyper U hypermarket. WooCommerce Store
API is wide open (no auth, no WAF signature) -- verified 2026-08-11:
currency_code=XPF, currency_minor_unit=0 (XPF has no subunit, so no
minor-unit scaling trap), 146 products across the catalog."""

from price_scraping.spiders._woo_base import WooBaseSpider


class HyperutahitiPfSpider(WooBaseSpider):
    name = "hyperutahiti_pf"
    allowed_domains = ["hyperutahiti.com"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://www.hyperutahiti.com/wp-json/wc/store/v1/products"
