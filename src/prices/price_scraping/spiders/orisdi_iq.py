"""Orisdi (Iraq) -- https://orisdi.com/. Perfume/fragrance retailer, prices
in USD despite serving the Iraqi market. Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class OrisdiIqSpider(ShopifyBaseSpider):
    name = "orisdi_iq"
    allowed_domains = ["orisdi.com"]
    base_url = "https://orisdi.com"
    currency = "USD"
    language = "ar"
