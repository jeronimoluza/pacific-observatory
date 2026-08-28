from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroDkSpider(KoroBaseSpider):
    name = "koro_dk"
    allowed_domains = ["bff.koro.com"]
    currency = "DKK"
    language = "da"
    ACCESS_KEY = "SWSCQK9ONZCXYNIZT1JVRVJSSG"
    DOMAIN = "www.koro.com/dk"
