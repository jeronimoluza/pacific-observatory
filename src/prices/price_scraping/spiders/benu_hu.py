"""BENU Hungary -- https://benu.hu/. National pharmacy chain webshop (OTC,
supplements, medical devices). Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class BenuHuSpider(ShopifyBaseSpider):
    name = "benu_hu"
    allowed_domains = ["benu.hu"]
    base_url = "https://benu.hu"
    currency = "HUF"
    language = "hu"
