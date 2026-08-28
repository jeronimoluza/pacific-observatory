"""Walmart / MasxMenos (Costa Rica) -- https://www.walmart.co.cr/. Walmart Centroamerica's CR banners (Walmart + MasxMenos) share one VTEX catalog at this host."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class WalmartCrSpider(VtexBaseSpider):
    name = "walmart_cr"
    allowed_domains = ["walmart.co.cr"]
    HOST = "www.walmart.co.cr"
    currency = "CRC"
    language = "es"
