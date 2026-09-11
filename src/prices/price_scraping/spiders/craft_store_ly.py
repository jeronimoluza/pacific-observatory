"""
Craft Store -- https://craft-store.ly/. Libya photography/videography
gear retailer (Insta360, Zhiyun, Boya, etc.). Standard WooCommerce Store
API. Confirmed live 2026-09-11: LYD prices at currency_minor_unit=2
(e.g. price "25000" -> LYD 250.00). 1979 products across 198 pages
(X-WP-Total header); page 1 vs page 2 returned zero overlapping ids
(distinct catalog, not a re-served page).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class CraftStoreLySpider(WooBaseSpider):
    name = "craft_store_ly"
    allowed_domains = ["craft-store.ly"]
    currency = "LYD"
    language = "en"
    BASE_URL = "https://craft-store.ly/wp-json/wc/store/v1/products"
