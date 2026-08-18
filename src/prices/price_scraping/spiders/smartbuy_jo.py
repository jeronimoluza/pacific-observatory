"""SmartBuy (Jordan) -- https://smartbuy-me.com/. Electronics and appliances
retailer. Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SmartbuyJoSpider(ShopifyBaseSpider):
    name = "smartbuy_jo"
    allowed_domains = ["smartbuy-me.com"]
    base_url = "https://smartbuy-me.com"
    currency = "JOD"
    language = "en"
