from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroSeSpider(KoroBaseSpider):
    name = "koro_se"
    allowed_domains = ["bff.koro.com"]
    currency = "SEK"
    language = "sv"
    ACCESS_KEY = "SWSCNKRHQ0XTBXOXZVHICZAZRA"
    DOMAIN = "www.koro.com/se"
