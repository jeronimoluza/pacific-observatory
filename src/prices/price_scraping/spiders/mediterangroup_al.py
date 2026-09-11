"""Mediteran Group (Albania) — https://mediterangroup.com. WooCommerce Store API.

WooCommerce Store API v1, unauthenticated. 1,861 products, 98 of the first 100 priced
(probed 2026-09-11). Albanian-language storefront (Tirana).
CURRENCY: the API reports prices.currency_code=EUR, not ALL. The base spider trusts the
API's reported code, so rows land as EUR. That is what the store actually quotes; do not
"fix" it to ALL without re-checking the rendered page.
Assortment is home textiles / household goods (bedding, towels, rugs, kitchen), so this
fills COICOP 05 for Albania rather than 01 -- Albania's existing manifests are Wolt
grocery/pharmacy only.
Variant rows repeat the parent title; the Store API exposes variations as separate
products, so duplicate names in the raw file are expected.
Page family parsed: API (/wp-json/wc/store/v1/products).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MediterangroupAlSpider(WooBaseSpider):
    name = "mediterangroup_al"
    allowed_domains = ["mediterangroup.com"]
    currency = "ALL"
    language = "sq"
    BASE_URL = "https://mediterangroup.com/wp-json/wc/store/v1/products"
