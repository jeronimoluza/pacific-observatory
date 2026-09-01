"""Locatel Venezuela -- https://www.locatel.com.ve/. Pharmacy/health-and-beauty chain, VTEX tenant."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class LocatelVeSpider(VtexBaseSpider):
    name = "locatel_ve"
    allowed_domains = ["locatel.com.ve"]
    HOST = "www.locatel.com.ve"
    currency = "VES"
    language = "es"
