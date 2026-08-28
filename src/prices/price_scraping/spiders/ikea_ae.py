"""IKEA UAE — https://www.ikea.com/ae/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaAeSpider(IkeaBaseSpider):
    name = "ikea_ae"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "ae"
    LANG = "en"
    currency = "AED"
    language = "en"
