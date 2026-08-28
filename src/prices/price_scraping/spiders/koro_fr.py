from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroFrSpider(KoroBaseSpider):
    name = "koro_fr"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "fr"
    ACCESS_KEY = "SWSCTVR2QLJRUZDQV0LWQ0VLNQ"
    DOMAIN = "www.koro.fr"
