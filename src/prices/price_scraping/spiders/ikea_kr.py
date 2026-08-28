"""IKEA South Korea — https://www.ikea.com/kr/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaKrSpider(IkeaBaseSpider):
    name = "ikea_kr"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "kr"
    LANG = "en"
    currency = "KRW"
    language = "en"
