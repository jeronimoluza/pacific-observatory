"""Shop Pohnpei (Micronesia) -- https://www.shoppohnpei.com/. Grocery store
(rice, canned fish, snacks). Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ShoppohnpeiFmSpider(ShopifyBaseSpider):
    name = "shoppohnpei_fm"
    allowed_domains = ["shoppohnpei.com"]
    base_url = "https://www.shoppohnpei.com"
    currency = "USD"
    language = "en"
