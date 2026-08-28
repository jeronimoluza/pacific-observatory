from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroAtSpider(KoroBaseSpider):
    name = "koro_at"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "de"
    ACCESS_KEY = "SWSCTLBKZXIXOFZSOTBWVFPANW"
    DOMAIN = "www.koro-shop.at"
