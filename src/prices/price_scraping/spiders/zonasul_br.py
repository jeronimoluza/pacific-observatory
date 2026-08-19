"""Zona Sul (Brazil) -- https://www.zonasul.com.br/. Premium full-line Rio de Janeiro chain (Grupo Bahamas)."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class ZonasulBrSpider(VtexBaseSpider):
    name = "zonasul_br"
    allowed_domains = ["zonasul.com.br"]
    HOST = "www.zonasul.com.br"
    currency = "BRL"
    language = "pt"
