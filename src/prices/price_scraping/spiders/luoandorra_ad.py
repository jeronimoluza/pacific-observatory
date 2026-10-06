"""Luo Andorra (Andorra) -- https://luoandorra.com/.

Andorran storefront (AD500 / +376 contact details on the site). Standard Shopify
catalog at /products.json?limit=250&page=N, read by the shared base class.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class LuoandorraAdSpider(ShopifyBaseSpider):
    name = "luoandorra_ad"
    allowed_domains = ["luoandorra.com"]
    base_url = "https://luoandorra.com"
    currency = "EUR"
    language = "es"
