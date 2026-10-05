"""Kave Home Andorra (Andorra) -- https://kavehome.ad/.

Andorran storefront (AD500 / +376 contact details on the site). Standard Shopify
catalog at /products.json?limit=250&page=N, read by the shared base class.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class KavehomeAdSpider(ShopifyBaseSpider):
    name = "kavehome_ad"
    allowed_domains = ["kavehome.ad"]
    base_url = "https://kavehome.ad"
    currency = "EUR"
    language = "ca"
