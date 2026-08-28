from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroDeSpider(KoroBaseSpider):
    name = "koro_de"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "de"
    ACCESS_KEY = "SWSCTNNXAGVLUVDQDHNCCVFQQW"
    DOMAIN = "www.korodrogerie.de"
