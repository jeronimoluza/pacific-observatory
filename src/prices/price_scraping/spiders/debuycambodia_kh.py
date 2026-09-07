"""Spider for Debuy Cambodia."""

from ._shopify_base import ShopifyBaseSpider


class DebuycambodiaKhSpider(ShopifyBaseSpider):
    name = "debuycambodia_kh"
    allowed_domains = [
        "debuycambodia.com.kh",
        "www.debuycambodia.com.kh",
    ]
    base_url = "https://www.debuycambodia.com.kh"
    currency = "USD"
    language = "en"
    custom_settings = ShopifyBaseSpider.custom_settings | {"CLOSESPIDER_ITEMCOUNT": 1000}
