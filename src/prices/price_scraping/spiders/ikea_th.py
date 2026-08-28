"""IKEA Thailand — https://www.ikea.com/th/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaThSpider(IkeaBaseSpider):
    name = "ikea_th"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "th"
    LANG = "en"
    currency = "THB"
    language = "en"
