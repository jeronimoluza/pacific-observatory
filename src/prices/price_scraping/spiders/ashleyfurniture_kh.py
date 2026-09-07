"""Spider for Ashley Furniture Homestore Cambodia."""

from ._shopify_base import ShopifyBaseSpider


class AshleyfurnitureKhSpider(ShopifyBaseSpider):
    name = "ashleyfurniture_kh"
    allowed_domains = [
        "shop.ashleyfurniturecambodia.com",
        "www.shop.ashleyfurniturecambodia.com",
    ]
    base_url = "https://shop.ashleyfurniturecambodia.com"
    currency = "USD"
    language = "en"
    custom_settings = ShopifyBaseSpider.custom_settings | {"CLOSESPIDER_ITEMCOUNT": 800}
