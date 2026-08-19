"""Spider for Blejeseshkoj (Kosovo) -- https://blejeseshkoj.com/. Classic
OpenCart `route=product/category&path=` hierarchy; the base class discovers
the full leaf-category set from the homepage nav."""

from price_scraping.spiders._opencart_base import OpencartBaseSpider


class BlejeseshkojSpider(OpencartBaseSpider):
    name = "blejeseshkoj"
    allowed_domains = ["blejeseshkoj.com"]
    currency = "EUR"
    language = "sq"
    LIMIT = 100
    NAV_URL = "https://blejeseshkoj.com/"
