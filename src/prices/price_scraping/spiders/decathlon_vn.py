"""Decathlon Vietnam — https://www.decathlon.vn/. Open Algolia search API, no WAF observed."""

from price_scraping.spiders._decathlon_base import DecathlonBaseSpider


class DecathlonVnSpider(DecathlonBaseSpider):
    name = "decathlon_vn"
    allowed_domains = ["decathlon.vn", "algolia.net"]
    APP_ID = "Z69HGH89IH"
    API_KEY = "911d17637d07cfd07475d590d045456a"
    INDEX = "prod_pim_v1_index"
    BASE_URL = "https://www.decathlon.vn"
    currency = "VND"
    language = "en"
