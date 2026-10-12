"""PADCI (Channel Islands) -- https://mypadci.com/. Open Shopify /products.json catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MypadciCiSpider(ShopifyBaseSpider):
    name = "mypadci_ci"
    allowed_domains = ["mypadci.com"]
    base_url = "https://mypadci.com"
    currency = "GBP"
    language = "en"
