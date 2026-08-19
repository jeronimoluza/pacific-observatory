"""La Union (Nicaragua) -- https://www.launion.com.ni/. Second independent VTEX tenant for NI (not the Walmart-CA one), meat confirmed."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class LaunionNiSpider(VtexBaseSpider):
    name = "launion_ni"
    allowed_domains = ["launion.com.ni"]
    HOST = "www.launion.com.ni"
    currency = "NIO"
    language = "es"
