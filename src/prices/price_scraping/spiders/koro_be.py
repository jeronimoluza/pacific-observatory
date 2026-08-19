from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroBeSpider(KoroBaseSpider):
    name = "koro_be"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "fr"
    ACCESS_KEY = "SWSCRMVGQZR5CHF6UKLWYUXJTG"
    DOMAIN = "www.koro.com/befr"
