"""JustMeat (Switzerland) butcher — https://justmeat.ch"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class JustmeatChSpider(ShopifyBaseSpider):
    name = "justmeat_ch"
    allowed_domains = ["justmeat.ch"]
    base_url = "https://justmeat.ch"
    currency = "CHF"
    language = "de"
