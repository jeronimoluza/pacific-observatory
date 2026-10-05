"""romerils.com (Channel Islands) -- https://www.romerils.com/. Open Shopify /products.json catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class RomerilsCiSpider(ShopifyBaseSpider):
    name = "romerils_ci"
    allowed_domains = ["romerils.com"]
    base_url = "https://www.romerils.com"
    currency = "GBP"
    language = "en"
