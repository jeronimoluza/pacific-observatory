"""Springs (Pakistan) -- https://springs.com.pk/. General household retailer
(crockery, skincare, confectionary, packaged food, kitchen appliances).
Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SpringsPkSpider(ShopifyBaseSpider):
    name = "springs_pk"
    allowed_domains = ["springs.com.pk"]
    base_url = "https://springs.com.pk"
    currency = "PKR"
    language = "en"
