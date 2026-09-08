"""Spider for Tappoo Fiji online storefront (Shopify)."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class TappooFjSpider(ShopifyBaseSpider):
    name = "tappoo_fj"
    allowed_domains = ["store.tappoo.com.fj"]
    base_url = "https://store.tappoo.com.fj"
    currency = "FJD"
    language = "en"
