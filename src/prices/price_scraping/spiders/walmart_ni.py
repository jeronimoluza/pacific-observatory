"""Walmart (Nicaragua) -- https://www.walmart.com.ni/. Full-line, fresh produce confirmed."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class WalmartNiSpider(VtexBaseSpider):
    name = "walmart_ni"
    allowed_domains = ["walmart.com.ni"]
    HOST = "www.walmart.com.ni"
    currency = "NIO"
    language = "es"
