"""GEO Gabon Shop (Gabon, Libreville, electronics, Shopify) — https://geogabon-shop.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class GeogabonGaSpider(ShopifyBaseSpider):
    name = "geogabon_ga"
    allowed_domains = ["geogabon-shop.com"]
    base_url = "https://geogabon-shop.com"
    currency = "XAF"
    language = "fr"
