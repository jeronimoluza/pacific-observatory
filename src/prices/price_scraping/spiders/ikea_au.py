"""IKEA Australia — https://www.ikea.com/au/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaAuSpider(IkeaBaseSpider):
    name = "ikea_au"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "au"
    LANG = "en"
    currency = "AUD"
    language = "en"
