"""
MercoCaribe Habana (Cuba) — https://habana.mercocaribe.com/.

One of Cuba's "MLC"-style virtual stores for foreign-card/diaspora-funded
purchases (delivery inside Cuba, payment in EUR/USD via international card),
not the domestic CUP retail network. Prices in EUR, not the country's
official CUP.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MercocaribeHabanaCuSpider(WooBaseSpider):
    name = "mercocaribe_habana_cu"
    allowed_domains = ["habana.mercocaribe.com"]
    currency = "EUR"
    language = "es"
    BASE_URL = "https://habana.mercocaribe.com/wp-json/wc/store/v1/products"
