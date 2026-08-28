"""Farmacity (Argentina) -- https://www.farmacity.com/. Pharmacy chain, independent VTEX tenant."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class FarmacityArSpider(VtexBaseSpider):
    name = "farmacity_ar"
    allowed_domains = ["farmacity.com"]
    HOST = "www.farmacity.com"
    currency = "ARS"
    language = "es"
