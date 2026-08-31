"""IKEA Oman — https://www.ikea.com/om/en/. Open JSON listing API, no WAF observed.

Same shared platform as ikea_ae/ikea_sa (see _ikea_base.py docstring).
Verified live 2026-08-31: /om/en/cat/products-products/ mega-nav yields 210
category keys; sik.search.blue.cdtapps.com/om/en/product-list-page returns
real OMR-priced items (e.g. HELMER storage unit at 25.00 OMR).
"""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaOmSpider(IkeaBaseSpider):
    name = "ikea_om"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "om"
    LANG = "en"
    currency = "OMR"
    language = "en"
