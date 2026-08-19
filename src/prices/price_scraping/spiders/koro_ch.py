from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroChSpider(KoroBaseSpider):
    name = "koro_ch"
    allowed_domains = ["bff.koro.com"]
    currency = "CHF"
    language = "de"
    ACCESS_KEY = "SWSCBLEWSWFEYXJWOVO2Y3ZMQQ"
    DOMAIN = "www.koro-shop.ch"
