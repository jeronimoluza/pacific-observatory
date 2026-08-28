"""
Assivito (Togo) — https://www.assivito.com/.

General local-products marketplace (agri/health, artisans, fashion, real
estate, vehicles); only category id 173 ("Produits transformes") is
genuinely food, so we scope to that category rather than walking the whole
non-food catalog.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class AssivitoTgSpider(WooBaseSpider):
    name = "assivito_tg"
    allowed_domains = ["assivito.com", "www.assivito.com"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://www.assivito.com/wp-json/wc/store/v1/products"
    CATEGORY_ID = 173
