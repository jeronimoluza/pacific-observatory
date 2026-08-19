"""
Spider for Supermercados Selectos (Puerto Rico) — https://www.selectoseasyshop.com/.

NCR Freshop tenant app_key=selectos, store_id=5988 (Guaynabo — 40-store
chain app-wide, 17,742 items at this one store). skip-based pagination
verified live (skip=0 vs skip=3 return different items, unlike the
walter_mart tenant which ignores offset entirely).
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class SelectosPrSpider(FreshopBaseSpider):
    name = "selectos_pr"
    currency = "USD"
    language = "es"

    APP_KEY = "selectos"
    STORE_ID = "5988"
