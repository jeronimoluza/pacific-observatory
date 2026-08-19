"""Decathlon Australia — https://www.decathlon.com.au/. Open Algolia search API, no WAF observed."""

from price_scraping.spiders._decathlon_base import DecathlonBaseSpider


class DecathlonAuSpider(DecathlonBaseSpider):
    name = "decathlon_au"
    allowed_domains = ["decathlon.com.au", "algolia.net"]
    APP_ID = "TBG2XI2W65"
    API_KEY = "2008d3d6a0c51b49bf51bb700248763c"
    INDEX = "prod_pim_v1_index"
    BASE_URL = "https://www.decathlon.com.au"
    currency = "AUD"
    language = "en"
