"""Fravega (Argentina) -- https://www.fravega.com/. Electronics/appliances chain, independent VTEX tenant."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class FravegaArSpider(VtexBaseSpider):
    name = "fravega_ar"
    allowed_domains = ["fravega.com"]
    HOST = "www.fravega.com"
    currency = "ARS"
    language = "es"
