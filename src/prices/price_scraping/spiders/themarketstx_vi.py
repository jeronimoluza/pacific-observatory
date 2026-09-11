"""
Spider for The Market St Croix (US Virgin Islands, Frederiksted).

NCR Freshop tenant app_key=plaza_extra_west (the app_key does NOT match the
brand -- The Market St Croix is Plaza Extra's west-island storefront),
store_id=4978 ("The Market St Croix", Frederiksted, VI).
Probed live 2026-09-11: total=20099 with unit_price populated. The sibling
store_id 4977 reports a higher total (24011) but null unit_price on every row --
catalog-only, do not switch to it.
Note some price strings are multi-buy ("3 for $1.00"); the base spider uses the
numeric unit_price field, not the display string, so those land correctly.
Page family parsed: API (api.freshop.ncrcloud.com/2/products).
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class ThemarketstxViSpider(FreshopBaseSpider):
    name = "themarketstx_vi"
    currency = "USD"
    language = "en"

    APP_KEY = "plaza_extra_west"
    STORE_ID = "4978"
