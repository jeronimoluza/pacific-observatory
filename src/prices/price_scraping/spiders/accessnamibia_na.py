"""
Access Namibia -- https://accessnamibia.com/ (consumer electronics and
accessories retailer, Namibia).

Standard Shopify storefront. Open, unauthenticated catalog at
/products.json?limit=250&page=N. Storefront reports currency NAD
(Shopify.currency.active = "NAD", cart.json currency = "NAD", checkout
country "NA") -- not ZAR.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class AccessnamibiaNaSpider(ShopifyBaseSpider):
    name = "accessnamibia_na"
    allowed_domains = ["accessnamibia.com"]
    base_url = "https://accessnamibia.com"
    currency = "NAD"
    language = "en"
