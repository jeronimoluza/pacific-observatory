"""Down to Earth (Ireland) — https://downtoearth.ie/. Shopify storefront."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class DowntoearthIeSpider(ShopifyBaseSpider):
    name = "downtoearth_ie"
    allowed_domains = ["downtoearth.ie"]
    base_url = "https://downtoearth.ie"
    currency = "EUR"
    language = "en"
