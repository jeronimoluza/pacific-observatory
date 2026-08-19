from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroNlSpider(KoroBaseSpider):
    name = "koro_nl"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "nl"
    ACCESS_KEY = "SWSCDELAV0LHAHRPQLFUM1JIRA"
    DOMAIN = "www.koro.com/nl"
