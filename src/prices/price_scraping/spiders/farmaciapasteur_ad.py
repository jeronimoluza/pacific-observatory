"""Farmacia Pasteur (Andorra) -- https://farmaciapasteur.com/.

Andorran storefront (AD500 / +376 contact details on the site). Standard Shopify
catalog at /products.json?limit=250&page=N, read by the shared base class.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class FarmaciapasteurAdSpider(ShopifyBaseSpider):
    name = "farmaciapasteur_ad"
    allowed_domains = ["farmaciapasteur.com"]
    base_url = "https://farmaciapasteur.com"
    currency = "EUR"
    language = "ca"
