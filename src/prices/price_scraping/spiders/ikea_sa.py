"""IKEA Saudi Arabia — https://www.ikea.com/sa/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaSaSpider(IkeaBaseSpider):
    name = "ikea_sa"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "sa"
    LANG = "en"
    currency = "SAR"
    language = "en"
