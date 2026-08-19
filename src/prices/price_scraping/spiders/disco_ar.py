"""Disco (Argentina) -- https://www.disco.com.ar/. Cencosud AR banner, same VTEX tenant/account family as Jumbo AR and Vea AR -- high catalog overlap, still a distinct banner/price point."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class DiscoArSpider(VtexBaseSpider):
    name = "disco_ar"
    allowed_domains = ["disco.com.ar"]
    HOST = "www.disco.com.ar"
    currency = "ARS"
    language = "es"
