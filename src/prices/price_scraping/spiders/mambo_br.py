"""Mambo (Brazil) -- https://www.mambo.com.br/. Sao Paulo interior full-line chain, fresh produce confirmed."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class MamboBrSpider(VtexBaseSpider):
    name = "mambo_br"
    allowed_domains = ["mambo.com.br"]
    HOST = "www.mambo.com.br"
    currency = "BRL"
    language = "pt"
