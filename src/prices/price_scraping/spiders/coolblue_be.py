from price_scraping.spiders._coolblue_base import CoolblueBaseSpider


class CoolblueBeSpider(CoolblueBaseSpider):
    name = "coolblue_be"
    allowed_domains = ["coolblue.be", "www.coolblue.be"]
    currency = "EUR"
    language = "nl"
    BASE_URL = "https://www.coolblue.be"
    CATEGORY_PREFIX = "nl/"
