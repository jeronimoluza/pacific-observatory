"""Kywi (Ecuador) -- https://www.kywi.com.ec/. Hardware/home-improvement chain, independent VTEX tenant. Apex domain has an expired SSL cert; www subdomain has a valid one."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class KywiEcSpider(VtexBaseSpider):
    name = "kywi_ec"
    allowed_domains = ["kywi.com.ec"]
    HOST = "www.kywi.com.ec"
    currency = "USD"
    language = "es"
