"""
Langerhans Pharmacy -- https://langerhanspharmacy.com/ (Namibia).

Standard Shopify storefront. Open, unauthenticated catalog at
/products.json?limit=250&page=N. Storefront reports currency NAD
(Shopify.currency.active = "NAD", cart.json currency = "NAD") -- not ZAR.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class LangerhansNaSpider(ShopifyBaseSpider):
    name = "langerhans_na"
    allowed_domains = ["langerhanspharmacy.com"]
    base_url = "https://langerhanspharmacy.com"
    currency = "NAD"
    language = "en"
