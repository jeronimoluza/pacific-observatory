from price_scraping.spiders._coolblue_base import CoolblueBaseSpider


class CoolblueNlSpider(CoolblueBaseSpider):
    name = "coolblue_nl"
    allowed_domains = ["coolblue.nl", "www.coolblue.nl"]
    currency = "EUR"
    language = "nl"
    BASE_URL = "https://www.coolblue.nl"
    CATEGORY_PREFIX = ""
