"""DodoMarket (Mauritius, Shopify) — https://dodomarket.mu/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class DodomarketMuSpider(ShopifyBaseSpider):
    name = "dodomarket_mu"
    allowed_domains = ["dodomarket.mu"]
    base_url = "https://dodomarket.mu"
    currency = "MUR"
    language = "en"
