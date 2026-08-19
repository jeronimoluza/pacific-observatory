"""Walmart (Honduras) -- https://www.walmart.com.hn/. Full-line, fresh produce confirmed."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class WalmartHnSpider(VtexBaseSpider):
    name = "walmart_hn"
    allowed_domains = ["walmart.com.hn"]
    HOST = "www.walmart.com.hn"
    currency = "HNL"
    language = "es"
