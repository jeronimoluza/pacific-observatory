"""IKEA Philippines — https://www.ikea.com/ph/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaPhSpider(IkeaBaseSpider):
    name = "ikea_ph"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "ph"
    LANG = "en"
    currency = "PHP"
    language = "en"
