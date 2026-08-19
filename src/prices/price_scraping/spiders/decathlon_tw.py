"""Decathlon Taiwan — https://www.decathlon.tw/. Open Algolia search API, no WAF observed."""

from price_scraping.spiders._decathlon_base import DecathlonBaseSpider


class DecathlonTwSpider(DecathlonBaseSpider):
    name = "decathlon_tw"
    allowed_domains = ["decathlon.tw", "algolia.net"]
    APP_ID = "LBAG9DUR10"
    API_KEY = "c73b38e1124588810d937807d6810f82"
    INDEX = "prod_pim_v1_index"
    BASE_URL = "https://www.decathlon.tw"
    LANG_SUFFIX = "zh"
    SPORT_FACET_FIELD = "sport_zh"
    currency = "TWD"
    language = "zh"
