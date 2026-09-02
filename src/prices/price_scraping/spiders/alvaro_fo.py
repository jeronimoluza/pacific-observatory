"""Alvaró (Faroe Islands) -- https://www.alvaro.fo/. Tórshavn retailer with
same-day delivery in Tórshavn/Hoyvík/Argir. Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class AlvaroFoSpider(ShopifyBaseSpider):
    name = "alvaro_fo"
    allowed_domains = ["alvaro.fo", "www.alvaro.fo"]
    base_url = "https://www.alvaro.fo"
    currency = "DKK"
    language = "fo"
