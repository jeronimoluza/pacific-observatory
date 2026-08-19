"""Decathlon Hong Kong SAR — https://www.decathlon.com.hk/. Open Algolia search API, no WAF observed."""

from price_scraping.spiders._decathlon_base import DecathlonBaseSpider


class DecathlonHkSpider(DecathlonBaseSpider):
    name = "decathlon_hk"
    allowed_domains = ["decathlon.com.hk", "algolia.net"]
    APP_ID = "P7HDNSD47U"
    API_KEY = "a6930b815bbc3cbc03dc89b48935baa0"
    INDEX = "prod_pim_v1_index"
    BASE_URL = "https://www.decathlon.com.hk"
    currency = "HKD"
    language = "en"
