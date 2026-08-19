"""SAKI Stores (Chuuk/Pohnpei/Kosrae, Micronesia) -- https://saki4you.com/.
General hypermarket (groceries, household, small appliances). Shopify catalog
is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class Saki4YouFmSpider(ShopifyBaseSpider):
    name = "saki4you_fm"
    allowed_domains = ["saki4you.com"]
    base_url = "https://saki4you.com"
    currency = "USD"
    language = "en"
