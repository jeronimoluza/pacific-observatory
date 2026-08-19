"""Savegnago (Brazil) -- https://www.savegnago.com.br/. Sao Paulo interior full-line chain, fresh produce confirmed."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class SavegnagoBrSpider(VtexBaseSpider):
    name = "savegnago_br"
    allowed_domains = ["savegnago.com.br"]
    HOST = "www.savegnago.com.br"
    currency = "BRL"
    language = "pt"
