"""Siman (El Salvador) -- https://www.siman.com/. www.siman.com is a country-selector hub for a
regional dept-store chain (SV/GT/NI/CR); the sv.siman.com subdomain is the actual VTEX tenant."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class SimanSvSpider(VtexBaseSpider):
    name = "siman_sv"
    allowed_domains = ["siman.com"]
    HOST = "sv.siman.com"
    currency = "USD"
    language = "es"
