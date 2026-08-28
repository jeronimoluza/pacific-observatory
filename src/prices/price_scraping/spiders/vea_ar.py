"""Vea (Argentina) -- https://www.vea.com.ar/. Cencosud AR discount banner, same VTEX tenant family as Jumbo AR and Disco AR."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class VeaArSpider(VtexBaseSpider):
    name = "vea_ar"
    allowed_domains = ["vea.com.ar"]
    HOST = "www.vea.com.ar"
    currency = "ARS"
    language = "es"
