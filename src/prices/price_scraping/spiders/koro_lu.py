from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroLuSpider(KoroBaseSpider):
    name = "koro_lu"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "fr"
    ACCESS_KEY = "SWSCZ3PPQMJTSKD5VFFOV0TTVA"
    DOMAIN = "www.koro.com/lufr"
