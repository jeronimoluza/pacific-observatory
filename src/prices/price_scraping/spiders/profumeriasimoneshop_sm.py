"""Profumeria Simone -- https://www.profumeriasimoneshop.com/ (perfumery, cosmetics, watches,
jewellery; San Marino shop since 1978).

PrestaShop with stock microdata cards; category URLs `/<id>-<slug>` with `?page=N`, so the shared
PrestashopBaseSpider walks it unchanged. EUR.
Page family: listing.
"""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class ProfumeriasimoneshopSmSpider(PrestashopBaseSpider):
    name = "profumeriasimoneshop_sm"
    allowed_domains = ["profumeriasimoneshop.com"]
    currency = "EUR"
    language = "it"
    HOME_URL = "https://www.profumeriasimoneshop.com/"
