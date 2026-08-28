"""
Spider for GoWell BD (Bangladesh) — https://gowellbd.com/.

WooCommerce Store API confirmed live 2026-08-18: GET
/wp-json/wc/store/v1/products?per_page=100&page=N -> 200, BDT minor-unit
JSON prices (currency_minor_unit=2). Page 1 vs page 2 confirmed to return
disjoint product ids (645 products / 65 pages at per_page=10, scaled to
per_page=100 for the live spider). Catalog is medical/health-equipment led
(anatomical models, BP monitors, thermometers, glucometers, supports) with
Beauty and Baby & Mom Care as secondary categories.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class GowellbdBdSpider(WooBaseSpider):
    name = "gowellbd_bd"
    allowed_domains = ["gowellbd.com"]
    currency = "BDT"
    language = "en"
    BASE_URL = "https://gowellbd.com/wp-json/wc/store/v1/products"
