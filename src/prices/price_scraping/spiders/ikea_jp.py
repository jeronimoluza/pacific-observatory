"""IKEA Japan — https://www.ikea.com/jp/en/. Open JSON listing API, no WAF observed."""

from price_scraping.spiders._ikea_base import IkeaBaseSpider


class IkeaJpSpider(IkeaBaseSpider):
    name = "ikea_jp"
    allowed_domains = ["ikea.com", "cdtapps.com"]
    MARKET = "jp"
    LANG = "en"
    currency = "JPY"
    language = "en"
