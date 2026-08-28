"""Scott Home Delivery (Mauritius, wine/spirits, Shopify) — https://scotthomedelivery.mu/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ScotthomedeliveryMuSpider(ShopifyBaseSpider):
    name = "scotthomedelivery_mu"
    allowed_domains = ["scotthomedelivery.mu"]
    base_url = "https://scotthomedelivery.mu"
    currency = "MUR"
    language = "en"
