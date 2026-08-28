from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroItSpider(KoroBaseSpider):
    name = "koro_it"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "it"
    ACCESS_KEY = "SWSCBFDGSKCXVLK3UDHRRW9QYG"
    DOMAIN = "www.koro-shop.it"
