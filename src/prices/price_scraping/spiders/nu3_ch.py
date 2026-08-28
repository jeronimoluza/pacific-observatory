"""nu3 Switzerland — https://www.nu3.ch/. Shopify storefront."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class Nu3ChSpider(ShopifyBaseSpider):
    name = "nu3_ch"
    allowed_domains = ["nu3.ch"]
    base_url = "https://www.nu3.ch"
    currency = "CHF"
    language = "de"
