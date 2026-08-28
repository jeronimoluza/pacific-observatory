from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroEsSpider(KoroBaseSpider):
    name = "koro_es"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "es"
    ACCESS_KEY = "SWSCRZN6OEPSTLUZAWXACDL4SW"
    DOMAIN = "www.koro.com/es"
