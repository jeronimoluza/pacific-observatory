from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroFiSpider(KoroBaseSpider):
    name = "koro_fi"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "fi"
    ACCESS_KEY = "SWSCEENBNMDEOUD5ZZBYQNJWNA"
    DOMAIN = "www.koro.com/fi"
