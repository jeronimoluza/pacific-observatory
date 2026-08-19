"""Dia Argentina -- https://diaonline.supermercadosdia.com.ar/. Discount/proximity format, packaged-goods heavy, thinner fresh section."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class DiaArSpider(VtexBaseSpider):
    name = "dia_ar"
    allowed_domains = ["supermercadosdia.com.ar"]
    HOST = "diaonline.supermercadosdia.com.ar"
    currency = "ARS"
    language = "es"
