"""Decathlon Thailand — https://www.decathlon.co.th/. Open Algolia search API, no WAF observed."""

from price_scraping.spiders._decathlon_base import DecathlonBaseSpider


class DecathlonThSpider(DecathlonBaseSpider):
    name = "decathlon_th"
    allowed_domains = ["decathlon.co.th", "algolia.net"]
    APP_ID = "G20XLWDZTC"
    API_KEY = "fe4a9b874f7a2c9efaf583a6c29d228f"
    INDEX = "prod_pim_v2_index"
    BASE_URL = "https://www.decathlon.co.th"
    currency = "THB"
    language = "en"
