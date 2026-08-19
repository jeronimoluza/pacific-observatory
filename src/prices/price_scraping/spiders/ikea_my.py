"""IKEA Malaysia — https://www.ikea.com/my/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaMySpider(IkeaBaseSpider):
    name = "ikea_my"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "my"
    LANG = "en"
    currency = "MYR"
    language = "en"
