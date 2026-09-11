"""
Spider for Plaza Extra East (US Virgin Islands, Christiansted).

NCR Freshop tenant app_key=plaza_extra_east, store_id=5186 ("Plaza Extra East",
Christiansted, St Croix, VI). Probed live 2026-09-11: total=17591 with unit_price
populated. Sibling store_id 5185 has a near-identical total but null unit_price
throughout -- catalog-only.
Page family parsed: API (api.freshop.ncrcloud.com/2/products).
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class PlazaextraeastViSpider(FreshopBaseSpider):
    name = "plazaextraeast_vi"
    currency = "USD"
    language = "en"

    APP_KEY = "plaza_extra_east"
    STORE_ID = "5186"
