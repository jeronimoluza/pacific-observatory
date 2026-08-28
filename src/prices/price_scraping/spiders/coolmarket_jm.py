"""
Spider for CoolMarket Groceries (Jamaica) — https://www.coolmarket.com/groceries.html.

Magento SSR HTML with data-price-amount markup throughout. Deep grocery
catalog (CSV: ~1,386 items). Standard Magento ?p=N pagination.
"""

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider


class CoolmarketJmSpider(MagentoSSRBaseSpider):
    name = "coolmarket_jm"
    allowed_domains = ["coolmarket.com"]
    currency = "JMD"
    language = "en"

    START_URLS = ["https://www.coolmarket.com/groceries.html"]
    PAGE_PARAM = "p"
