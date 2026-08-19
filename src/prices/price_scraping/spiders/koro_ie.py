from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroIeSpider(KoroBaseSpider):
    name = "koro_ie"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "en"
    ACCESS_KEY = "SWSCSFFHTZJRA1VBOFZ6RDHARW"
    DOMAIN = "www.koro.com/ie"
