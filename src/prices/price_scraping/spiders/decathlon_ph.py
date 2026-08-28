"""Decathlon Philippines — https://www.decathlon.ph/. Open Algolia search API, no WAF observed."""

from price_scraping.spiders._decathlon_base import DecathlonBaseSpider


class DecathlonPhSpider(DecathlonBaseSpider):
    name = "decathlon_ph"
    allowed_domains = ["decathlon.ph", "algolia.net"]
    APP_ID = "TQ8I7I4SV5"
    API_KEY = "f84be427ebd72a229919bcbeef1555dd"
    INDEX = "prod_pim_v2_index"
    BASE_URL = "https://www.decathlon.ph"
    currency = "PHP"
    language = "en"
