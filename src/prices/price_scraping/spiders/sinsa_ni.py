"""Sinsa (Nicaragua) -- https://www.sinsa.com.ni/. Hardware/home-improvement chain, independent VTEX tenant."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class SinsaNiSpider(VtexBaseSpider):
    name = "sinsa_ni"
    allowed_domains = ["sinsa.com.ni"]
    HOST = "www.sinsa.com.ni"
    currency = "NIO"
    language = "es"
