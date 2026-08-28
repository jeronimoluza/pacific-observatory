"""Walmart (El Salvador) -- https://www.walmart.com.sv/. Walmart Centroamerica banner, full-line, meat confirmed. El Salvador uses USD."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class WalmartSvSpider(VtexBaseSpider):
    name = "walmart_sv"
    allowed_domains = ["walmart.com.sv"]
    HOST = "www.walmart.com.sv"
    currency = "USD"
    language = "es"
