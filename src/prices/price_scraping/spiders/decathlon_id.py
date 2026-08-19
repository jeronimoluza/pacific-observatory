"""Decathlon Indonesia — https://www.decathlon.co.id/. Open Algolia search API, no WAF observed."""

from price_scraping.spiders._decathlon_base import DecathlonBaseSpider


class DecathlonIdSpider(DecathlonBaseSpider):
    name = "decathlon_id"
    allowed_domains = ["decathlon.co.id", "algolia.net"]
    APP_ID = "OODQBD265X"
    API_KEY = "868f375f2cbe82050e53035b4c9ed57a"
    INDEX = "prod_pim_v1_index"
    BASE_URL = "https://www.decathlon.co.id"
    currency = "IDR"
    language = "en"
