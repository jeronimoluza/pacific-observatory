"""The Lusaka Grocery Delivery Company (Zambia, Shopify) — https://lusakadelivery.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class LusakadeliverySpider(ShopifyBaseSpider):
    name = "lusakadelivery"
    allowed_domains = ["lusakadelivery.com"]
    base_url = "https://lusakadelivery.com"
    currency = "ZMW"
    language = "en"
